# snapshot-election-results

The goal of this repository is to help gather snapshots of election results
data and archive it for analysis.

## Related work
See [openelections/clarify](https://github.com/openelections/clarify)
(_Discover and parse results for jurisdictions that use Clarity\-based election systems_)
for a much cleaner set of code to do related things.

## Usage
Currently it contains the `mine_election.py` script, written in Python.
That currently only supports pulling results data from Clarify,
SOE Software's Clarity Election Night Reporting system, originally developed,
now owned by Scytl.

Each snapshot is stored in a simple Berkeley DB database.

The code is very immature and needs considerable work and documentation
to make it robust or easy to use without close familiarity with the code.

As hinted at in comments in the code
under _Configuration updates for a new election_,
the trickiest part is figuring out the right URLs to use when pulling the
results from a given election, and the URL path elements to use for each county.

See the code comments for some example URLs.
