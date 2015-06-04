#!/usr/bin/python
"""mine_election.py: archive election data and mine it for falloff / residual rate, and other data.
stores summary and csv files in database
(by default, ~/.config/electionaudits/clarity in Berkely DB format).

not working: Parses xml election results file from clarity, and saves data in database

Usage:
 mine_election.py -c 'Boulder/43040'

Gets any new county results and archives them in the database.
This will skip any for which we already have an up-to-date dump, and print what was gotten.

Files:
 summary.html          Container with "Last updated" timestamp, overall "Ballots Cast", but no contest results
 summary.zip archive   Just a summary.csv file in it, with contest results
 sum.json              Contest results in JSON format - used by javascript in summary.html
   e.g. http://results.enr.clarityelections.com/CO/Arapahoe/48372/123238/json/sum.json

Note that the summary.html file doesn't include the actual contest results.
But it does contain a "Last updated" timestamp and a "Ballots Cast" which can
be higher than even the 'ballots cast' column of a county-wide contest in the summary.csv.
That is typically because property owner ballots don't have county-wide races on them.

The url path for county results changes for each election.  Get it e.g. via copy-paste and edit from the html source for
 http://results.enr.clarityelections.com/CO/48370/122717/en/select-county.html
 For examples from around the county via http://www.reddit.com/domain/results.enr.clarityelections.com see /srv/voting/colorado/clarity-urls
 Search e.g.: site:results.enr.clarityelections.com 2014 general election 

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
add option to pick downloads (multiple files), via county name, or state-wide
 then make new object with timestamp and csv from that download
  (later collect data that way, add more files perhaps)

add option to dump various kinds of info from observations:
 write out csv (perhaps named with county and timestamp)
 timestamp and size of csv
 find data in csv or whatever
 print # ballots, turnout (% of registered)

figure out how to get county lists for Web01 style - for now get them by hand:
   navigate to 'counties reporting' tab, save file, grep `id="precinctsreporting', clean up with emacs macros

store a single class per version, rather than 3 db entries.
 and convert from old to new format when noticed

work more transparently with both new-style (Web01) and old-style clarity urls
figure out how to find last-updated for Web01 style

add etag checking, maybe last-modified-since to lower bandwidth demands
 any more efficient way to get version info than fetching redirect?
add a way to re-fetch stuff, or 

Get other formats of data also

Produce auditing data: raw margin, diluted margin, auditing required

Use shove for better reliability and cloud or git storage : Python Package Index https://pypi.python.org/pypi/shove/0.5.6

Check state-wide info vs county aggregates

add function / option to summarize db - range of timestamps, # entries etc.  do so after normal runs

 print summary of contents of database
 parse a collection of clarity downloads
 look for small vote counts, bad residuals, etc
 look at diffs between runs
 print last-updated date and ballot count

/srv/voting/colorado/2012/detail.xml

Example data
summary.zip csv file:

"line number","contest name","choice name","party name","total votes","percent of votes","registered voters","ballots cast","num County total","num County rptg","over votes","under votes"
1,"UNITED STATES SENATOR","Mark Udall","DEM",782549,44.52,2047458,1681230,64,39,"0","0"
2,"UNITED STATES SENATOR","Cory Gardner","REP",880925,50.12,2047458,1681230,64,39,"0","0"
3,"UNITED STATES SENATOR","Gaylon Kent","LIB",43431,2.47,2047458,1681230,64,39,"0","0"

detail.xml file:
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

Sample data from select-county.html
...
<td width="33%"><ul>
<li><a id="Adams" value="/Adams/51560/index.html" href="javascript:a('Adams');">Adams</a></li>
<li><a id="Alamosa" value="/Alamosa/51561/index.html" href="javascript:a('Alamosa');">Alamosa</a></li>
<li><a id="Arapahoe" value="/Arapahoe/51559/index.html" href="javascript:a('Arapahoe');">Arapahoe</a></li>
....

"""

import sys
import os
import logging
from optparse import OptionParser
import time
from datetime import datetime
import dateutil.parser
import urllib
import re
from collections import Counter
import lxml.etree as ET
import shelve
from zipfile import ZipFile
from pprint import pprint
from StringIO import StringIO
import dbhash

__version__ = "0.1.0"

parser = OptionParser(prog="template.py", version=__version__)

parser.add_option("-d", "--database",
  default=os.path.expanduser("~/.config/electionaudits/clarity"),
  help="file name for persistent data storage")

parser.add_option("-D", "--debuglevel",
  type="int", default=logging.WARNING,
  help="Set logging level to debuglevel: DEBUG=10, INFO=20,\n WARNING=30 (the default), ERROR=40, CRITICAL=50")

parser.add_option("-s", "--state",
  default='CO',
  help="State portion of clarity path, e.g. 'CO'")

parser.add_option("-c", "--countyids",
  help="Retrieve county results reported at this clarity URL path, e.g. 'Boulder/43040'")

parser.add_option("-f", "--find",
  help="Find given regular expression in csv files")

parser.add_option("-u", "--urlformat",
  default="/Web01",
  help="Format of urls")

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
    """Determine residual / falloff / undervote + overvote rate from the xml election results file.
    Yield a Residual object for each contest under root, with info on residuals etc"""

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

# Results for some states, e.g. Colorado 2014 general, no longer have a list of county ids listed, so do it by hand....

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

# First one, with no county name, is the CO state level
CO_counties_2014 = [
 '53335',
 'Adams/53338',
 'Alamosa/53339',
 'Arapahoe/53337',
 'Archuleta/53340',
 'Baca/53341',
 'Bent/53342',
 'Boulder/53343',
 'Broomfield/53344',
 'Chaffee/53345',
 'Cheyenne/53346',
 'Clear_Creek/53347',
 'Conejos/53348',
 'Costilla/53349',
 'Crowley/53350',
 'Custer/53351',
 'Delta/53352',
 'Denver/53353',
 'Dolores/53354',
 'Douglas/53355',
 'Eagle/53356',
 'Elbert/53357',
 'El_Paso/53358',
 'Fremont/53359',
 'Garfield/53360',
 'Gilpin/53361',
 'Grand/53362',
 'Gunnison/53363',
 'Hinsdale/53364',
 'Huerfano/53365',
 'Jackson/53366',
 'Jefferson/53336',
 'Kiowa/53367',
 'Kit_Carson/53368',
 'Lake/53369',
 'La_Plata/53370',
 'Larimer/53371',
 'Las_Animas/53372',
 'Lincoln/53373',
 'Logan/53374',
 'Mesa/53375',
 'Mineral/53376',
 'Moffat/53377',
 'Montezuma/53378',
 'Montrose/53379',
 'Morgan/53380',
 'Otero/53381',
 'Ouray/53382',
 'Park/53383',
 'Phillips/53384',
 'Pitkin/53385',
 'Prowers/53386',
 'Pueblo/53387',
 'Rio_Blanco/53388',
 'Rio_Grande/53389',
 'Routt/53390',
 'Saguache/53391',
 'San_Juan/53392',
 'San_Miguel/53393',
 'Sedgwick/53394',
 'Summit/53395',
 'Teller/53396',
 'Washington/53398',
 'Weld/53399',
 'Yuma/53400',
]

CO_counties = CO_counties_2014

version_re = re.compile(r'summary.html","\./(?P<version>[\d]*)"')
county_re = re.compile(r'value="/(?P<county>[^/]*)/(?P<id>[^/]*)/index.html')

def main(parser):
    """Collect and/or mine election data from a clarity election-night-reporting site

    For "county" option, fetch each county record to see if we have the latest.
    If not fetch it and add it to the database

    """

    (options, args) = parser.parse_args()

    #configure the root logger.  Without filename, default is StreamHandler with output to stderr. Default level is WARNING
    logging.basicConfig(level=options.debuglevel)   # ..., format='%(message)s', filename= "/file/to/log/to", filemode='w' )

    logging.debug("options: %s; args: %s", options, args)

    logging.log(60, "Start at %s.  Using database: %s" % (datetime.isoformat(datetime.now()), options.database))

    db = shelve.open(options.database)

    # ~/py/mine_election.py -D 20 -c 53704 -d clarity-KY-2014 2>&1 | tee -a 53704.out
    if options.countyids:
        if options.countyids == "53335":
            ids = CO_counties_2014
        else:
            ids = [options.countyids]

        for id in ids:  # ['Rio_Grande/43086']:
            path = "%s/%s/" % (options.state, id)
            morePaths = retrieve(path, db, options)

            for countyPath in morePaths:
                path = "%s/%s/" % (options.state, countyPath)
                retrieve(path, db, options)

    if options.find:
        print "find: '%s'" % options.find
        for k, v in db.iteritems():
            if "CO-5" in k  and  "summary.zip" in k:
                print "key: %s" % k

                zipf = StringIO(v)
                files = ZipFile(zipf, "r")
                for f in files.namelist():
                    logging.debug("  file: %s" % f)
                    if f != "summary.csv":
                        logging.error("Error - got file named %s in zip file, not summary.csv" % f)
                    csvf = files.open(f)
                    csv = csvf.read()

                    matches = re.finditer(options.find, csv)
                    for m in matches:
                        print m.groups()

    db.close()

def retrieve(path, db, options):
    """
    retrieve the given paths from clarity, and put in db if there is new data.
    return any possible future paths to fetch
    """

    urlprefix = "http://results.enr.clarityelections.com/"

    logging.info("Fetch redirect for %s from %s" % (path, urlprefix + path))
    url = urlprefix + path
    try:
        stream = urllib.urlopen(url)
    except Exception, e:
         logging.error("urllib error on url '%s':\n %s" % (url, e))
         return []

    redirect_html = stream.read()
    logging.debug("Redirect text: %s" % redirect_html)

    match = version_re.search(redirect_html)
        
    if match:
        version = match.group('version')
    else:
        logging.error("No version number in %s" % url)
        return []

    try:
        logging.debug("Match for version: %s" % version)
        summary_url = urlprefix + "%s/%s%s/en/summary.html" % (path, version, options.urlformat)
        # => e.g.  http://results.enr.clarityelections.com/CO/Boulder/43040/110810/en/summary.html
        csvz_url = urlprefix + "%s/%s/reports/summary.zip" % (path, version)
        # http://results.enr.clarityelections.com/CO/51557/138497/en/select-county.html
        select_county_url = urlprefix + "%s/%s%s/en/select-county.html" % (path, version, options.urlformat)

    except:
        logging.error("No match for %s" % path)

    logging.info("Full summary url: %s" % summary_url)

    summary_filen = path.replace("/", "-") + "-" + str(version) + "/en/summary.html"
    csvz_filen = path.replace("/", "-") + "-" + str(version) + "/reports/summary.zip"

    summary = db.get(summary_filen, None)

    if summary:
        # Get existing data
        logging.info("Already have summary, length %d, url: %s" % (len(summary), summary_filen))
        csvz = db[csvz_filen]
        lastupdated_field = db.get(version, None)
        if lastupdated_field:
            lastupdated_ts = lastupdated_field[0]
        else:
            lastupdated_ts = "unknown"

    else:
        logging.critical("Retrieving new results from %s" % summary_url)
        summary = urllib.urlopen(summary_url).read()
        db[summary_filen] = summary
        logging.info("summary file length: %d" % len(summary))
        logging.log(5, "summary file: %s" % summary)

        logging.info("Retrieving csvz file: %s" % csvz_url)
        csvz = urllib.urlopen(csvz_url).read()
        db[csvz_filen] = csvz

        match = re.search(r'ast updated[^;]*;(?P<lastupdated>[^<]*)<', summary)
        try:
            lastupdated = match.group('lastupdated')
            lastupdated_ts = dateutil.parser.parse(lastupdated)
        except Exception, e:
            logging.info("No lastupdated on url '%s':\nFile:\n%s" % (summary_url, e))
            logging.debug("No lastupdated on url '%s':\nFile:\n%s\n %s" % (summary_url, summary, e))
            lastupdated_ts = datetime.isoformat(datetime.now()) + " retrieved"

        db[version] = (str(lastupdated_ts), summary_filen)

    logging.info("Version: %s, updated %s, file %s" % (version, str(lastupdated_ts), summary_filen))

    zipf = StringIO(csvz)
    files = ZipFile(zipf, "r")
    for f in files.namelist():
        logging.debug("  file: %s" % f)
        if f != "summary.csv":
            logging.error("Error - got file named %s in zip file, not summary.csv" % f)
        csvf = files.open(f)
        csv = csvf.read()
        logging.debug("  file length: %d" % len(csv))

    logging.log(5, "csv file:\n%s" % csv)

    morePaths = []

    if "/" not in path[3:]:
        logging.info("Get select-county.html at %s" % select_county_url)
        countyList = urllib.urlopen(select_county_url).read()

        logging.log(5, "countyList = %s" % countyList)

        counties = re.findall(county_re, countyList)
        if len(counties) == 0:
            logging.info("Didn't find any counties in select-county.html:\n%s" % countyList)

        for (county, id) in counties:
            countyPath = "%s/%s" % (county, id)
            logging.debug("found county %s" % countyPath)
            morePaths.append(countyPath)

    if False:
        """
        Work with xml format objects, find ballotCast, residuals of 
        """

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

    time.sleep(1)

    return morePaths

"""
print "temporarily init root for interactive examination of detail.xml (from )"
detail_xml = open(detail_xml_name)
root = ET.parse(detail_xml).getroot()
"""

if __name__ == "__main__":
    main(parser)
