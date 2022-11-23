#!/usr/bin/env python
"""
Plot contest margin trends by county

See also: http://0.0.0.0:8888/notebooks/neal/.config/electionaudits/clarity-2022/dump/margin_trends.ipynb

TODO:
 Sort order of appearance of counties, or at least their labels in legend?
 Add a grid
 reduce blank space around subplot
 get legend outside subplot, or not overlapping anything
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import fileinput

COUNTIES_BY_SIZE = {
'Colorado': 0,	 # all 63 counties being audited
'El Paso': 1,
'Denver': 2,
'Arapahoe': 3,
'Jefferson': 4,
'Adams': 5,
'Douglas': 6,
'Larimer': 7,
'Weld': 8,
'Boulder': 9,
'Pueblo': 10,
'Mesa': 11,
'Broomfield': 12,
'Garfield': 13,
'La Plata': 14,
'Eagle': 15,
'Fremont': 16,
'Montrose': 17,
'Delta': 18,
'Summit': 19,
'Morgan': 20,
'Elbert': 21,
'Montezuma': 22,
'Routt': 23,
'Teller': 24,
'Logan': 25,
'Chaffee': 26,
'Otero': 27,
'Park': 28,
'Pitkin': 29,
'Gunnison': 30,
'Alamosa': 31,
'Grand': 32,
'Las Animas': 33,
'Archuleta': 34,
'Moffat': 35,
'Prowers': 36,
'Rio Grande': 37,
'Yuma': 38,
'Clear Creek': 39,
'San Miguel': 40,
'Conejos': 41,
'Lake': 42,
'Kit Carson': 43,
'Huerfano': 44,
'Rio Blanco': 45,
'Saguache': 46,
'Crowley': 47,
'Gilpin': 48,
'Bent': 49,
'Lincoln': 50,
'Custer': 51,
'Ouray': 52,
'Washington': 53,
'Phillips': 54,
'Costilla': 55,
'Baca': 56,
'Dolores': 57,
'Sedgwick': 58,
'Cheyenne': 59,
'Kiowa': 60,
'Jackson': 61,
'Mineral': 62,
'Hinsdale': 63,
'San Juan': 64,
}


"""
display(HTML("<style>.container { width:100% !important; }</style>"))
display(HTML("<style>.output_result { max-width:100% !important; }</style>"))
"""

plt.rcParams['figure.figsize'] = 13, 8

def load_csv(filename):
    "Read in csv from filename, related info, return dataframe"

    df = pd.read_csv(filename)
    print("Columns: %s" % str(' '.join(df.columns)))
    print("Descriptive statistics for numeric columns via describe():")
    # display(df.describe())
    return df

# csvfile = "boebert.csv"  #argv

csvfile = sys.stdin

df = load_csv(csvfile)

df['ts'] = pd.to_datetime(df.timestamp, infer_datetime_format=True)
df['county_id'] = pd.factorize(df['county'])[0]
df['cid'] = [COUNTIES_BY_SIZE[p.county.replace('_', ' ')] for p in df.itertuples()]

fig = plt.figure(); ax = fig.add_subplot()

# need to sort?

for county in df.county.unique():
    label = county
    if county == '115903':
        label = "statewide"
    df[df.county == county].plot.line('ts', 'pct_votes', ax=ax, label=label)

plt.show()
