# bartdepart
Real-time BART Departure LED Display

# Installing
```
python3.11 -m pip install .
```

# Running
```
WLED_IP=192.168.8.133 BART_API_KEY=YOUR-API-KEY-HERE bartdepart -n -s nbrk -d South
```

# References
[BART Station Abbreviations](https://api.bart.gov/docs/overview/abbrev.aspx)
```
Station Abbreviations
Abbr	Station Name
12th	12th St. Oakland City Center
16th	16th St. Mission (SF)
19th	19th St. Oakland
24th	24th St. Mission (SF)
ashb	Ashby (Berkeley)
antc	Antioch
balb	Balboa Park (SF)
bayf	Bay Fair (San Leandro)
bery	Berryessa / North San Jose
cast	Castro Valley
civc	Civic Center (SF)
cols	Coliseum
colm	Colma
conc	Concord
daly	Daly City
dbrk	Downtown Berkeley
dubl	Dublin/Pleasanton
deln	El Cerrito del Norte
plza	El Cerrito Plaza
embr	Embarcadero (SF)
frmt	Fremont
ftvl	Fruitvale (Oakland)
glen	Glen Park (SF)
hayw	Hayward
lafy	Lafayette
lake	Lake Merritt (Oakland)
mcar	MacArthur (Oakland)
mlbr	Millbrae
mlpt	Milpitas
mont	Montgomery St. (SF)
nbrk	North Berkeley
ncon	North Concord/Martinez
oakl	Oakland Int'l Airport
orin	Orinda
pitt	Pittsburg/Bay Point
pctr	Pittsburg Center
phil	Pleasant Hill
powl	Powell St. (SF)
rich	Richmond
rock	Rockridge (Oakland)
sbrn	San Bruno
sfia	San Francisco Int'l Airport
sanl	San Leandro
shay	South Hayward
ssan	South San Francisco
ucty	Union City
warm	Warm Springs/South Fremont
wcrk	Walnut Creek
wdub	West Dublin
woak	West Oakland
Note: The abbreviation ASBY for Ashby is also accepted for backwards compatibility with the BART GTFS feed. This is a deprecated abbreviation and should not be used for current and future development.
```
