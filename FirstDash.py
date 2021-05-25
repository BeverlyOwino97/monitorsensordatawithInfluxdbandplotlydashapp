import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Output, Input
from flask import send_from_directory
import os
from influxdb import InfluxDBClient
from influxdb import DataFrameClient
import pandas as pd
from pytz import timezone
from pandas import DataFrame, Series
from pandas.io.json import json_normalize
from datetime import datetime, timedelta
import plotly.graph_objs as go
import numpy as np


# read database
def read_db(db_name, measurement, period):
    # read  from database and fill data into pandas dataframe
    client = DataFrameClient(host     = '35.230.100.15',
                             port     = 8086,
                             username = 'admin',
                             password = 'bK2eCWuuAJHTgPRE',
                             database='db_name',
                             ssl=True)
    #result = client.query("select * from \"distance\" where time > now() - 24h and \"channelID\" = \'1395826\'")
    result = client.query('select * from ' + measurement + ' where time > now()-' + period, chunked=True)
    column = next(iter(result))
    data   = result[column]
    # convert utc time to local time
    data.index = data.index.tz_convert('Europe/Berlin')
    # plotly tries to use utc time first, so remove timezone information:
    # https://github.com/plotly/plotly.py/blob/6f9621a611da36f10678c9d9c8c784f55e472429/plotly/utils.py#L263
    data.index = data.index.tz_localize(None)
    return data

    # create layout object
def get_layout(data, item, yaxis_title):
    min_x = data.index[0] if (data is not None and not data.empty) else -1
    max_x = data.index[-1] if (data is not None and not data.empty) else 1
    min_y = data[item].min()-4. if (data is not None and not data.empty) else -1
    max_y = data[item].max()+4. if (data is not None and not data.empty) else 1
    return {
            'font'          : {'color' : 'rgb(240,240,240)'},
            'title'         : item,
            'plot_bgcolor'  : '#242424',
            'paper_bgcolor' : '#242424',
            'line'          : {'color' : 'rgb(224,72,66)'},
            'marker'        : {'color' : 'rgb(224,72,66)'},
            'xaxis'         : {
                              'title'     : 'time',
                              'range'     : [min_x, max_x],
                              'tickcolor' : 'rgb(80,80,80)',
                              'gridcolor' : 'rgb(80,80,80)',
                              'linecolor' : 'rgb(80,80,80)'
            },
            'yaxis'         : {
                              'title'     : yaxis_title,
                              'range'     : [min_y, max_y],
                              'tickcolor' : 'rgb(80,80,80)',
                              'gridcolor' : 'rgb(80,80,80)',
                              'linecolor' : 'rgb(80,80,80)'
            }
    }

    # create data object
def get_data(data, item, color):
    return {
          'x'      : data.index,
          'y'      : data[item],
          'name'   : 'lines+markers',
          'mode'   : 'lines+markers',
          'marker' : {
                     'color' : color,
                     'line'  : {'color' : color}
          },
          'line'   : {
                      'color' : color,
          }
    }

    # default data
db_name     = 'techgsm'
measurement = 'distance'
period      = '1d'
data        = read_db(db_name, measurement, period)
# dash
app  = dash.Dash()

app.layout = html.Div(
    [
        html.Link(
            rel  = 'stylesheet',
            href = '/static/css/main.css'
        ),
        html.H1('Sensor Data'),
        html.Div([
            html.Div([
                # dropdown for selecting measurement
                html.Label('Select measurement:'),
                dcc.Dropdown(
                    id        = 'dropdown-measurement',
                    options   = [
                        #{'label': 'raw data',               'value': 'data_raw'},
                        #{'label': 'averaged over 1 minute', 'value': 'autogen.mean_60s'},
                        #{'label': 'averaged over 1 hour',   'value': 'autogen.mean_1h'},
                        #{'label': 'averaged over 1 day',    'value': 'autogen.mean_1d'},
                        {'label':'CHANNELID=1353435','value': 'distance'},
                        {'label':'CHANNELID=1353435','value': 'Field2'},
                    ],
                    value     = 'distance',
                    clearable = False
                ),
            ]),
            html.Div([
                # dropdown for selecting period
                html.Label('Select Period:'),
                dcc.Dropdown(
                    id        = 'dropdown-period',
                    options   = [
                        {'label': '1 min',   'value': '1m'},
                        {'label': '10 min',  'value': '10m'},
                        {'label': '1 hour',  'value': '1h'},
                        {'label': '1 day',   'value': '1d'},
                        {'label': '1 week',  'value': '1w'},
                        {'label': '1 month', 'value': '4w'}
                    ],
                    value     = '1d',
                    clearable = False
                )
            ]),
            html.Div([
                # dropdown for selecting update interval
                # since infinity or no interval is not posible,
                # use maximum permitted time: 2147483647 (about 24.86 days)
                html.Label('Select update interval:'),
                dcc.Dropdown(
                    id        = 'dropdown-interval',
                    options   = [
                        {'label': 'every 5 seconds',  'value': 5*1000},
                        {'label': 'every 10 seconds', 'value': 10*1000},
                        {'label': 'every minute',     'value': 60*1000},
                        {'label': 'every hour',       'value': 60*60*1000},
                        {'label': 'every day',        'value': 24*60*60*1000},
                        {'label': 'never',            'value': 2147483647}
                    ],
                    value     = 60*1000,
                    clearable = False
                )
            ])
        ],
        className = 'dropdowns'
        ),
        # waterlevel graph
        dcc.Graph(id      = 'graph-waterlevel',
                  figure  = {
                        'data'   : [get_data(data, 'field1', 'rgb(224,72,66)')],
                        'layout' : get_layout(data, 'field1', 'field1 &cm')
                  }
        ),
        dcc.Interval(id          = 'interval-component',
                     n_intervals = 0
        ),
    ]
)

app  = dash.Dash()
app.config.suppress_callback_exceptions = True
# css file
@app.server.route('/static/<path:path>')
def static_file(path):
    static_folder = os.path.join(os.getcwd(), 'static')
    return send_from_directory(static_folder, path)

# update interval
@app.callback(Output('interval-component', 'interval'),
              [Input('dropdown-interval', 'value')
              ])
def update_interval(value):
    return value


# update temperature graph
@app.callback(Output('graph-waterlevel', 'figure'),
              [Input('interval-component', 'n_intervals'),
               Input('dropdown-measurement', 'value'),
               Input('dropdown-period', 'value')
              ])
def update_graph(n, dropdown_measurement, dropdown_period):
    # read database
    measurement = dropdown_measurement
    period      = dropdown_period
    data        = read_db(db_name, measurement, period)
    # return data and layout
    return {
        'data'   : [get_data(data, 'field1', 'rgb(224,72,66)')],
        'layout' : get_layout(data, 'field1', 'field1 &cm')
    }

if __name__ == '__main__' : 
    app.run_server(port = 8050)