
# BartDepart

Use the BART API and the WLED python library to create a LED departure display.


## Hardware

- [LED Strip Supplier](https://www.superlightingled.com/rgb-flexible-led-strip-lights-c-3_26.html)
- [LED Controller](https://www.athom.tech/blank-1/wled-high-power-led-strip-controller)
- [Power Supply](https://www.amazon.com/dp/B07BJMJQ64)


## WLED Open Source LED Control Software

- [WLED Project Repository](https://github.com/wled/WLED)
- [Python: WLED API Client](https://github.com/frenck/python-wled)


## BART API

[API Documentation](https://www.bart.gov/schedules/developers/api)

Sample Query:
```bash
https://api.bart.gov/api/etd.aspx?cmd=etd&orig=19th&key=MW9S-E7SL-26DU-VV8V&json=y
```

Formatted Query Result:
```json
{
  "?xml": {
    "@version": "1.0",
    "@encoding": "utf-8"
  },
  "root": {
    "@id": "1",
    "uri": {
      "#cdata-section": "http://api.bart.gov/api/etd.aspx?cmd=etd&orig=19th&json=y"
    },
    "date": "07/08/2025",
    "time": "12:02:47 PM PDT",
    "station": [
      {
        "name": "19th St. Oakland",
        "abbr": "19TH",
        "etd": [
          {
            "destination": "Antioch",
            "abbreviation": "ANTC",
            "limited": "0",
            "estimate": [
              {
                "minutes": "12",
                "platform": "3",
                "direction": "North",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "67",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "31",
                "platform": "3",
                "direction": "North",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "51",
                "platform": "3",
                "direction": "North",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              }
            ]
          },
          {
            "destination": "Berryessa",
            "abbreviation": "BERY",
            "limited": "0",
            "estimate": [
              {
                "minutes": "5",
                "platform": "2",
                "direction": "South",
                "length": "6",
                "color": "ORANGE",
                "hexcolor": "#ff9933",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "25",
                "platform": "2",
                "direction": "South",
                "length": "6",
                "color": "ORANGE",
                "hexcolor": "#ff9933",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "45",
                "platform": "2",
                "direction": "South",
                "length": "6",
                "color": "ORANGE",
                "hexcolor": "#ff9933",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              }
            ]
          },
          {
            "destination": "Millbrae",
            "abbreviation": "MLBR",
            "limited": "0",
            "estimate": [
              {
                "minutes": "10",
                "platform": "2",
                "direction": "South",
                "length": "6",
                "color": "RED",
                "hexcolor": "#ff0000",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "31",
                "platform": "2",
                "direction": "South",
                "length": "6",
                "color": "RED",
                "hexcolor": "#ff0000",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "51",
                "platform": "2",
                "direction": "South",
                "length": "6",
                "color": "RED",
                "hexcolor": "#ff0000",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              }
            ]
          },
          {
            "destination": "Pittsburg/Bay Point",
            "abbreviation": "PITT",
            "limited": "0",
            "estimate": [
              {
                "minutes": "2",
                "platform": "3",
                "direction": "North",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "22",
                "platform": "3",
                "direction": "North",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "42",
                "platform": "3",
                "direction": "North",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              }
            ]
          },
          {
            "destination": "Richmond",
            "abbreviation": "RICH",
            "limited": "0",
            "estimate": [
              {
                "minutes": "13",
                "platform": "1",
                "direction": "North",
                "length": "6",
                "color": "ORANGE",
                "hexcolor": "#ff9933",
                "bikeflag": "1",
                "delay": "173",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "18",
                "platform": "1",
                "direction": "North",
                "length": "6",
                "color": "RED",
                "hexcolor": "#ff0000",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "31",
                "platform": "1",
                "direction": "North",
                "length": "6",
                "color": "ORANGE",
                "hexcolor": "#ff9933",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              }
            ]
          },
          {
            "destination": "SF Airport",
            "abbreviation": "SFIA",
            "limited": "0",
            "estimate": [
              {
                "minutes": "3",
                "platform": "2",
                "direction": "South",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "15",
                "platform": "2",
                "direction": "South",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              },
              {
                "minutes": "23",
                "platform": "2",
                "direction": "South",
                "length": "8",
                "color": "YELLOW",
                "hexcolor": "#ffff33",
                "bikeflag": "1",
                "delay": "0",
                "cancelflag": "0",
                "dynamicflag": "0"
              }
            ]
          }
        ]
      }
    ],
    "message": ""
  }
}
```
