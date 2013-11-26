#!/usr/bin/python
"""mine_election.py: mine election data for falloff / residual rate, etc
Parses xml election results file from clarity, and saves data in database
(by default, ~/.config/electionaudits/clarity in Berkely DB format).

Usage:
For each new election, update county "url path" see below.

Get any new county results and archive them in the database.
This will skip any for which we already have an up-to-date dump, and print what was gotten.

 mine_election.py -c

Files:
 summary.html          Container with "Last updated" timestamp, overall "Ballots Cast", but no contest results
 summary.zip archive   Just a summary.csv file in it, with contest results
 sum.json              Contest results in JSON format - used by javascript in summary.html
   e.g. http://results.enr.clarityelections.com/CO/Arapahoe/48372/123238/json/sum.json

Note that the summary.html file doesn't include the actual contest results.
But it does contain a "Last updated" timestamp and a "Ballots Cast" which can
be higher than even the 'ballots cast' column of a county-wide contest in the summary.csv.
That is typically because property owner ballots don't have county-wide races on them.

%InsertOptionParserUsage%

For now, to look at data, analyze csv, use ~/py/notebooks/corla.ipynb

or....

db = shelve.open("/home/neal/.config/electionaudits/clarity")
len(db.keys())
db.keys()
arap = db['Arapahoe-48372-123238reports/summary.zip']
wash = db['Washington-48433-122703reports/summary.zip']
wr = open('/tmp/wash.zip', 'w')
wr.write(wash)
wr.close()

TODO:
Get other formats of data also

Produce auditing data: raw margin, diluted margin, auditing required

Use shove for better reliability and cloud or git storage : Python Package Index https://pypi.python.org/pypi/shove/0.5.6

Check state-wide info
Get data from other jurisdictions:
 http://results.enr.clarityelections.com/FL/Dade/42008/113201/en/summary.html
 http://results.enr.clarityelections.com/FL/Martin/42442/112876/en/summary.html
 http://results.enr.clarityelections.com/FL/Orange/43105/112625/en/summary.html
 http://results.enr.clarityelections.com/NJ/Cape_May/48214/122334/en/summary.html
 search e.g. FL site:results.enr.clarityelections.com

clean up retrieval of csvs.  they're really zips.  write decoding, dumping sw.
add function / option to summarize db - range of timestamps, # entries etc.  do so after normal runs

 print summary of contents of database
 parse a collection of clarity downloads
 look for small vote counts, bad residuals, etc
 look at diffs between runs
 print last-updated date and ballot count

/srv/voting/colorado/2012/detail.xml

/ElectionResult/Contest/Choice/@totalVotes
        <Choice key="10" text="Yes" totalVotes="1307728">
            <VoteType name="Total Votes" votes="1307728">
                <County name="Adams" votes="94616" />
/ElectionResult/Contest/Choice/VoteType/County/@votes
      1 ElectionResult/ElectionVoterTurnout/@ballotsCast
      1 ElectionResult/ElectionVoterTurnout/Counties
     64 ElectionResult/ElectionVoterTurnout/Counties/County
     64 ElectionResult/ElectionVoterTurnout/Counties/County/@ballotsCast

PRESIDENT AND VICE PRESIDENT
AMENDMENT
REGENT OF THE UNIVERSITY OF COLORADO - AT LARGE
STATE BOARD OF EDUCATION
REGENT OF THE UNIVERSITY OF COLORADO - CONGRESSIONAL DISTRICT
STATE SENATE - DISTRICT
STATE REPRESENTATIVE - DISTRICT
REGIONAL TRANSPORTATION DISTRICT DIRECTOR
COLORADO COURT OF APPEALS
JUDICIAL DISTRICT
COUNTY COURT

Sample redirect from http://results.enr.clarityelections.com/CO/Boulder/43040/
which is really intended for 
  http://results.enr.clarityelections.com/CO/Boulder/43040/110810/en/summary.html
and the csv report at e.g.
  http://results.enr.clarityelections.com/CO/Rio_Grande/43086/111231/reports/summary.zip
----
 <html><head>
                    <script src="./110810/js/version.js" type="text/javascript"></script>
                    <script type="text/javascript">TemplateRedirect("summary.html","./110810", "", "");</script>
                    </head></html>
----

"""

import sys
import os
import logging
from optparse import OptionParser
import dateutil.parser
import urllib
import re
from collections import Counter
import lxml.etree as ET
import shelve

__version__ = "0.1.0"

parser = OptionParser(prog="template.py", version=__version__)

parser.add_option("-s", "--storage",
  default=os.path.expanduser("~/.config/electionaudits/clarity"),
  help="storage file name for persistence of data")

parser.add_option("-d", "--debuglevel",
  type="int", default=logging.WARNING,
  help="Set logging level to debuglevel: DEBUG=10, INFO=20,\n WARNING=30 (the default), ERROR=40, CRITICAL=50")

parser.add_option("-c", "--county",
  action="store_true", default=False,
  help="Retrieve county reports")

# incorporate OptionParser usage documentation in our docstring
__doc__ = __doc__.replace("%InsertOptionParserUsage%\n", parser.format_help())

detail_xml_name="/srv/voting/colorado/2012/detail.xml"

class Residual(object):
    def __init__(self, **attributes):
        "Store all values offered"
        for k, v in attributes.items():
            setattr(self, k, v)

    def __str__(self):
        return "residual: %5.2f\t%s" % (100.0 - (100.0 * self.total / self.ballotsCast), self.name)

def residuals(root):
    "yield a Residual object for each contest under root, with info on residuals etc"

    ballotsCast = int(xpath_unique(root, '//ElectionResult/ElectionVoterTurnout/@ballotsCast'))
    ballots_by_county = {}

    for county in root.xpath('//ElectionResult/ElectionVoterTurnout/Counties/County'):
        ballots_by_county[county.attrib['name']] = int(county.attrib['ballotsCast'])

    for contest in root.xpath('//ElectionResult/Contest'):
        contest_name = xpath_unique(contest, "@text")

        choiceTotalVotes = contest.xpath('Choice/@totalVotes')
        total = sum(int(votes) for votes in choiceTotalVotes)

        votes_by_county = Counter()
        for choice in contest.xpath('Choice'):
            for county in choice.xpath('VoteType/County'):
                votes_by_county[county.attrib['name']] += int(county.attrib['votes'])

        by_county = {}
        for name, votes in votes_by_county.items():
            if votes > ballots_by_county[name]:
                print "Warning: votes > ballots (%d vs %d) in %s for %s" % (votes, ballots_by_county[name], name, contest_name)
            by_county[name] = Residual(name = name,
                                      total = votes,
                                      ballotsCast = ballots_by_county[name],
                                      residual = 100 - (100.0 * votes / ballots_by_county[name]) )

        yield(Residual(name = contest_name,
                      total = total,
                      ballotsCast = ballotsCast,
                      residual = 100.0 - (100.0 * total / ballotsCast),
                      by_county = by_county ))


        """

        'ElectionResult/ElectionVoterTurnout/Counties/County/@ballotsCast'
        'ElectionResult/Contest/Choice/VoteType/County/@votes'

        print("total: %d  ballots: %d  residual: %.2f for %s" % (total, ballotsCast, 100.0 - (100.0 * total / ballotsCast), xpath_unique(contest, "@text")))

        sorted(residuals(root), key=lambda i: i['residual'], reverse=True)

        choices = contest.iterfind('Choice')
        in root.xpath('//ElectionResult/Contest/Choice/@totalVotes'):
        """

def xpath_unique(parent, path):
    nodes = parent.xpath(path)
    nnodes = len(nodes)
    if nnodes < 1:
        print("Error: path %s not found in %s" % (path, root))
        return None
    elif nnodes > 1:
        print("Error: path %s found %d times in %s" % (path, nnodes, root))
    return nodes[0]

# The url path for county results changes for each election.  Get it e.g. via copy-paste and edit from the html source for
#  http://results.enr.clarityelections.com/CO/48370/122717/en/select-county.html
# 

# First one, with no county name, is the CO state level
CO_counties_2012 = [
 '43032',
 'Adams/43035',
 'Alamosa/43036',
 'Arapahoe/43034',
 'Archuleta/43037',
 'Baca/43038',
 'Bent/43039',
 'Boulder/43040',
 'Broomfield/43041',
 'Chaffee/43042',
 'Cheyenne/43043',
 'Clear_Creek/43044',
 'Conejos/43045',
 'Costilla/43046',
 'Crowley/43047',
 'Custer/43048',
 'Delta/43049',
 'Denver/43050',
 'Dolores/43051',
 'Douglas/43052',
 'Eagle/43053',
 'El_Paso/43055',
 'Elbert/43054',
 'Fremont/43056',
 'Garfield/43057',
 'Gilpin/43058',
 'Grand/43059',
 'Gunnison/43060',
 'Hinsdale/43061',
 'Huerfano/43062',
 'Jackson/43063',
 'Jefferson/43033',
 'Kiowa/43064',
 'Kit_Carson/43065',
 'La_Plata/43067',
 'Lake/43066',
 'Larimer/43068',
 'Las_Animas/43069',
 'Lincoln/43070',
 'Logan/43071',
 'Mesa/43072',
 'Mineral/43073',
 'Moffat/43074',
 'Montezuma/43075',
 'Montrose/43076',
 'Morgan/43077',
 'Otero/43078',
 'Ouray/43079',
 'Park/43080',
 'Phillips/43081',
 'Pitkin/43082',
 'Prowers/43083',
 'Pueblo/43084',
 'Rio_Blanco/43085',
 'Rio_Grande/43086',
 'Routt/43087',
 'Saguache/43088',
 'San_Juan/43089',
 'San_Miguel/43090',
 'Sedgwick/43091',
 'Summit/43092',
 'Teller/43093',
 'Washington/43095',
 'Weld/43096',
 'Yuma/43097',
]

# First one, with no county name, is the CO state level
CO_counties_2013 = [
 '48370',
 'Adams/48373',
 'Alamosa/48374',
 'Arapahoe/48372',
 'Archuleta/48375',
 'Baca/48376',
 'Bent/48377',
 'Boulder/48378',
 'Broomfield/48379',
 'Chaffee/48380',
 'Cheyenne/48381',
 'Clear_Creek/48382',
 'Conejos/48383',
 'Costilla/48384',
 'Crowley/48385',
 'Custer/48386',
 'Delta/48387',
 'Denver/48388',
 'Dolores/48389',
 'Douglas/48390',
 'Eagle/48391',
 'El_Paso/48393',
 'Elbert/48392',
 'Fremont/48394',
 'Garfield/48395',
 'Gilpin/48396',
 'Grand/48397',
 'Gunnison/48398',
 'Hinsdale/48399',
 'Huerfano/48400',
 'Jackson/48401',
 'Jefferson/48371',
 'Kiowa/48402',
 'Kit_Carson/48403',
 'La_Plata/48405',
 'Lake/48404',
 'Larimer/48406',
 'Las_Animas/48407',
 'Lincoln/48408',
 'Logan/48409',
 'Mesa/48410',
 'Mineral/48411',
 'Moffat/48412',
 'Montezuma/48413',
 'Montrose/48414',
 'Morgan/48415',
 'Otero/48416',
 'Ouray/48417',
 'Park/48418',
 'Phillips/48419',
 'Pitkin/48420',
 'Prowers/48421',
 'Pueblo/48422',
 'Rio_Blanco/48423',
 'Rio_Grande/48424',
 'Routt/48425',
 'Saguache/48426',
 'San_Juan/48427',
 'San_Miguel/48428',
 'Sedgwick/48429',
 'Summit/48430',
 'Teller/48431',
 'Washington/48433',
 'Weld/48434',
 'Yuma/48435',
]

CO_counties = CO_counties_2013

version_re = re.compile(r'summary.html","\./(?P<version>[\d]*)"')

def main(parser):
    """Collect and/or mine election data from a clarity election-night-reporting site

    For "county" option, fetch each county record to see if we have the latest.
    If not fetch it and add it to the database

    """

    (options, args) = parser.parse_args()

    #configure the root logger.  Without filename, default is StreamHandler with output to stderr. Default level is WARNING
    logging.basicConfig(level=options.debuglevel)   # ..., format='%(message)s', filename= "/file/to/log/to", filemode='w' )

    logging.debug("options: %s; args: %s", options, args)

    print("Using database: %s" % options.storage)

    db = shelve.open(options.storage)

    if options.county:
        #for path in ['Rio_Grande/43086']:
        for path in CO_counties:  # ['Rio_Grande/43086']:
            stream = urllib.urlopen("http://results.enr.clarityelections.com/CO/" + path)
            logging.debug("Fetch redirect for %s" % path)

            redirect_html = stream.read()
            logging.debug("Redirect text: %s" % redirect_html)

            match = version_re.search(redirect_html)
            version = match.group('version')
            try:
                logging.debug("Match for version: %s" % version)
                zip_url = "http://results.enr.clarityelections.com/CO/%s/%s/reports/summary.zip" % (path, version)
                # => e.g.  http://results.enr.clarityelections.com/CO/Boulder/43040/110810/en/summary.html
                summary_url = "http://results.enr.clarityelections.com/CO/%s/%s/en/summary.html" % (path, version)
                csv_url = "http://results.enr.clarityelections.com/CO/%s/%s/reports/summary.zip" % (path, version)
            except:
                logging.error("No match for %s" % path)

            logging.info("Full url: %s" % zip_url)
            #zip_filen = path.replace("/", "-") + "-" + str(version) + ".zip"
            #zip_file = ZipFile(urllib.urlopen(zip_url, zip_filen))
            
            summary_filen = path.replace("/", "-") + "-" + str(version) + "/en/summary.html"
            csv_filen = path.replace("/", "-") + "-" + str(version) + "reports/summary.zip"

            summary = db.get(summary_filen, None)
            if not summary:
                logging.info("Retrieving file: %s" % summary_filen)
                summary = urllib.urlopen(summary_url).read()
                db[summary_filen] = summary

                logging.info("Retrieving csv file: %s" % csv_url)
                csv = urllib.urlopen(csv_url).read()
                db[csv_filen] = csv

                match = re.search(r'Last updated[^;]*;(?P<lastupdated>[^<]*)<', summary)
                try:
                    lastupdated = match.group('lastupdated')
                    lastupdated_ts = dateutil.parser.parse(lastupdated)
                except Exception, e:
                    logging.error("No lastupdated on url '%s':\n %s" % (summary_url, e))
                    continue

                db[version] = (str(lastupdated_ts), summary_filen)
                print version, db[version]

    if False:
        detail_xml = open(detail_xml_name)
        root = ET.parse(detail_xml).getroot()

        electionName = xpath_unique(root, '//ElectionResult/ElectionName').text
        timestamp = xpath_unique(root, '//ElectionResult/Timestamp').text
        ballotsCast = int(xpath_unique(root, '//ElectionResult/ElectionVoterTurnout/@ballotsCast'))

        print "Election Name: %s\nTimestamp: %s\nBallots Cast: %d\n" % (electionName, timestamp, ballotsCast)

        resid = list(residuals(root))

        # avoid some local races
        top_resid = [r for r in resid if r.residual <= 70.0]

        for r in sorted(top_resid, key=lambda r: r.residual):
            print r

        contests = {}
        for r in resid:
            contests[r.name] = r

        p = contests['PRESIDENT AND VICE PRESIDENT']

        print "Residual %      Votes    Ballots  County name"
        for c in sorted(p.by_county.values(), key=lambda c: c.residual):
            print "%10.2f %10d %10d  %s" % (c.residual, c.total, c.ballotsCast, c.name)

    db.close()

"""
print "temporarily init root for interactive examination of detail.xml (from )"
detail_xml = open(detail_xml_name)
root = ET.parse(detail_xml).getroot()
"""

if __name__ == "__main__":
    main(parser)
