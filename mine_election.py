#!/usr/bin/python
"""mine_election.py: mine election data for falloff / residual rate, etc
Parses xml election results file from clarity

TODO:
 parse a collection of clarity downloads

"""

from collections import Counter
import lxml.etree as ET

"""
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

"""

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

detail_xml = open(detail_xml_name)
root = ET.parse(detail_xml).getroot()

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
