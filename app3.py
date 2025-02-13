import os
import dash
from dash import dcc, html, Input, Output, dash_table
import plotly.express as px
import geopandas as gpd
import pandas as pd
import dash_leaflet as dl
import json

# Initialize Dash app
app = dash.Dash(__name__)
server = app.server

# Custom CSS for the popup
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .custom-popup .leaflet-popup-content-wrapper {
                padding: 0;
                overflow: hidden;
                background: transparent;
                border: none;
                box-shadow: none;
            }
            .custom-popup .leaflet-popup-content {
                margin: 0;
                background: transparent;
            }
            .custom-popup .leaflet-popup-tip {
                display: none;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Card style
card_style = {
    'padding': '15px',
    'borderRadius': '5px',
    'backgroundColor': 'white',
    'boxShadow': '2px 2px 2px lightgrey',
    'margin': '10px',
    'width': '200px',
    'display': 'inline-block',
    'textAlign': 'center'
}

# Rwanda's bounding box coordinates
RWANDA_BOUNDS = [[-2.8389, 28.8617], [-1.0474, 30.8989]]

def clean_name(name):
    """Clean facility and sector names for better matching"""
    if pd.isna(name):
        return ""
    return str(name).strip().split(' ')[0].lower()

def load_data():
    try:
        print("\nDEBUG INFORMATION:")
        
        # Read the malaria data
        print("Loading malaria shapefile...")
        df_malaria = gpd.read_file('rwa_adm4_2006_NISR_WGS1984_20181002.shp')
        df_selected = df_malaria[['ADM2_EN', 'ADM3_EN', 'geometry']].copy()
        
        # Read CSV file
        print("\nLoading malaria cases CSV...")
        df2 = pd.read_csv('malaria_cases.csv')
        
        # Clean names
        df2.loc[:, 'Cleaned_Facility'] = df2['facility_name'].apply(clean_name)
        df_selected.loc[:, 'Cleaned_ADM3_EN'] = df_selected['ADM3_EN'].apply(clean_name)
        
        # Rename columns
        df_renamed = df_selected.rename(columns={'ADM2_EN': 'District', 'ADM3_EN': 'Sector'}).copy()
        
        # Merge data
        merged_df = pd.merge(df_renamed, df2, 
                           left_on='Cleaned_ADM3_EN', 
                           right_on='Cleaned_Facility', 
                           how='inner').copy()
        
        # Process dates
        merged_df['Date'] = pd.to_datetime(merged_df['Date'])
        merged_df['Year'] = merged_df['Date'].dt.year
        merged_df['Month'] = merged_df['Date'].dt.month

        # Read and load wetland data
        print("\nLoading wetlands shapefile...")
        df_wetlands = gpd.read_file('Wetlands_and_Swamps_Final.shp')
        df_wetlands = df_wetlands.to_crs("EPSG:4326")
        df_wetlands = df_wetlands[df_wetlands.geometry.notna()]
        df_wetlands['Area_km2'] = df_wetlands['Area_1']
        
        return merged_df, df_wetlands
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        return None, None

# Load the data
df_malaria, df_wetlands = load_data()
merged_df = df_malaria  # Store the actual merged data

if merged_df is not None and df_wetlands is not None:
    # Create wetlands table
    wetlands_table = dash_table.DataTable(
        data=df_wetlands[['Nom', 'Area_1']].rename(columns={'Area_1': 'Area_km2'}).round(2).to_dict('records'),
        columns=[
            {"name": "Wetland Name", "id": "Nom"},
            {"name": "Area (km²)", "id": "Area_km2"}
        ],
        style_table={'height': '300px', 'overflowY': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '10px'},
        style_header={
            'backgroundColor': '#f8f9fa',
            'fontWeight': 'bold',
            'border': '1px solid black'
        },
        style_data_conditional=[{
            'if': {'row_index': 'odd'},
            'backgroundColor': '#f8f9fa'
        }],
        page_size=10
    )
    
    # Get year range from merged_df
    min_year = merged_df['Year'].min()
    max_year = merged_df['Year'].max()
    
    # Convert wetlands to GeoJSON
    wetlands_geojson = json.loads(df_wetlands.to_json())
	# Create layout
    app.layout = html.Div([
        # Title
        html.H1("Rwanda malaria outbreak dashboard", 
                style={'textAlign': 'center', 'color': '#2c3e50', 'padding': '20px'}),
        
        # Filters Container
        html.Div([
            # District Selector
            html.Div([
                html.Label('Select District:', style={'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='district-dropdown',
                    options=[{'label': d, 'value': d} for d in sorted(merged_df['District'].unique())],
                    value=merged_df['District'].unique()[0]
                )
            ], style={'width': '30%', 'display': 'inline-block', 'marginRight': '20px'}),
            
            # Year Range Selector
            html.Div([
                html.Label('Select Year Range:', style={'fontWeight': 'bold'}),
                dcc.RangeSlider(
                    id='year-range-slider',
                    min=min_year,
                    max=max_year,
                    value=[min_year, max_year],
                    marks={str(year): str(year) for year in range(min_year, max_year + 1)},
                    step=None
                )
            ], style={'width': '60%', 'display': 'inline-block'})
        ], style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '10px', 'margin': '20px'}),
        
        # Loading spinner for the entire content
        dcc.Loading(
            id="loading-1",
            type="circle",
            children=[
                # Summary Statistics Cards
                html.Div(id='summary-stats', style={'textAlign': 'center', 'margin': '20px'}),
                
                # Maps Container
                html.Div([
                    # Malaria Cases Map
                    html.Div([
                        html.H3("Malaria Cases Distribution", style={'textAlign': 'center'}),
                        html.Div([
                            # Map Legend
                            html.Div([
                                html.H4("Map Legend", style={'marginBottom': '10px'}),
                                html.Div([
                                    html.Div([
                                        html.Div(style={
                                            'width': '20px',
                                            'height': '20px',
                                            'backgroundColor': '#2ecc71',
                                            'display': 'inline-block',
                                            'marginRight': '5px'
                                        }),
                                        html.Span("Increasing Cases")
                                    ], style={'marginBottom': '5px'}),
                                    html.Div([
                                        html.Div(style={
                                            'width': '20px',
                                            'height': '20px',
                                            'backgroundColor': '#e74c3c',
                                            'display': 'inline-block',
                                            'marginRight': '5px'
                                        }),
                                        html.Span("Decreasing Cases")
                                    ])
                                ], style={'padding': '10px', 'backgroundColor': 'white', 'borderRadius': '5px'})
                            ], style={'position': 'absolute', 'top': '10px', 'right': '10px', 'zIndex': '1000'}),
                            
                            dl.Map([
                                dl.TileLayer(),
                                dl.GeoJSON(id='geojson-layer', data={}),
                                dl.LayerGroup(id='marker-layer')
                            ], 
                            center=[-1.9403, 29.8739],
                            zoom=8,
                            style={'height': '400px', 'width': '100%'},
                            bounds=RWANDA_BOUNDS,
                            maxBounds=RWANDA_BOUNDS)
                        ], style={'position': 'relative'})
                    ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
                    
                    # Wetlands Map
                    html.Div([
                        html.H3("Wetlands Distribution", style={'textAlign': 'center'}),
                        dl.Map(
                            center=[-1.9403, 29.8739],
                            zoom=8,
                            maxBounds=RWANDA_BOUNDS,
                            minZoom=8,
                            children=[
                                dl.TileLayer(),
                                dl.Rectangle(
                                    bounds=RWANDA_BOUNDS,
                                    color='green',
                                    weight=2,
                                    fill=False,
                                    opacity=1
                                ),
                                dl.GeoJSON(
                                    data=wetlands_geojson,
                                    id='wetlands-layer',
                                    options=dict(
                                        style=dict(
                                            fillColor='red',
                                            weight=2,
                                            opacity=1,
                                            color='white',
                                            dashArray='3',
                                            fillOpacity=0.7
                                        )
                                    ),
                                    hoverStyle=dict(fillColor='#ff7800', fillOpacity=0.8)
                                )
                            ],
                            style={'height': '400px', 'width': '100%'}
                        )
                    ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'})
                ], style={'margin': '20px'}),
                
                # Wetlands Table
                html.Div([
                    html.H3("Wetlands Information", style={'textAlign': 'center'}),
                    wetlands_table
                ], style={'margin': '20px', 'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '5px'}),
                
                # Charts Container
                html.Div([
                    # Bar Chart
                    html.Div([
                        dcc.Graph(id='facility-bar-chart', style={'height': '300px'})
                    ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
                    
                    # Line Chart
                    html.Div([
                        dcc.Graph(id='monthly-trend-chart', style={'height': '300px'})
                    ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'})
                ], style={'margin': '20px'}),
                
                # Data Table
                html.Div([
                    html.H3("Detailed Data", style={'textAlign': 'center'}),
                    dash_table.DataTable(
                        id='cases-table',
                        style_table={'height': '300px', 'overflowY': 'auto'},
                        style_cell={'textAlign': 'left', 'padding': '10px'},
                        style_header={
                            'backgroundColor': '#f8f9fa',
                            'fontWeight': 'bold',
                            'border': '1px solid black'
                        },
                        style_data_conditional=[{
                            'if': {'row_index': 'odd'},
                            'backgroundColor': '#f8f9fa'
                        }],
                        page_size=10
                    )
                ], style={'margin': '20px'})
            ]
        )
    ])

    @app.callback(
        [Output('cases-table', 'data'),
         Output('cases-table', 'columns'),
         Output('geojson-layer', 'data'),
         Output('marker-layer', 'children'),
         Output('facility-bar-chart', 'figure'),
         Output('monthly-trend-chart', 'figure'),
         Output('summary-stats', 'children')],
        [Input('district-dropdown', 'value'),
         Input('year-range-slider', 'value')]
    )
    def update_dashboard(selected_district, year_range):
        try:
            # Filter data
            mask = (
                (merged_df['District'] == selected_district) &
                (merged_df['Year'] >= year_range[0]) &
                (merged_df['Year'] <= year_range[1])
            )
            district_data = merged_df.loc[mask].copy()
            
            # Aggregate data for table
            agg_data = district_data.groupby('facility_name')['Malaria_cases_OPD'].agg([
                ('Total Cases', 'sum'),
                ('Average Cases', 'mean'),
                ('Maximum Cases', 'max')
            ]).reset_index()
            agg_data = agg_data.round(2)
            
            # Create columns for table
            columns = [{"name": i, "id": i} for i in agg_data.columns]
            
            # Create GeoJSON
            geojson_data = {
                'type': 'FeatureCollection',
                'features': json.loads(district_data.geometry.to_json())
            }
            
            # Create markers with cards
            markers = []
            for _, row in agg_data.iterrows():
                facility_data = district_data[district_data['facility_name'] == row['facility_name']]
                if len(facility_data) > 0:
                    lat = facility_data.iloc[0].geometry.centroid.y
                    lon = facility_data.iloc[0].geometry.centroid.x
                    
                    # Calculate month-over-month growth
                    facility_monthly = facility_data.groupby(['Year', 'Month'])['Malaria_cases_OPD'].sum().reset_index()
                    if len(facility_monthly) > 1:
                        last_month = facility_monthly.iloc[-1]['Malaria_cases_OPD']
                        prev_month = facility_monthly.iloc[-2]['Malaria_cases_OPD']
                        mom_growth = ((last_month - prev_month) / prev_month * 100) if prev_month != 0 else 0
                    else:
                        mom_growth = 0
                    
                    # Create popup cards
                    card_color = "#2ecc71" if mom_growth >= 0 else "#e74c3c"
                    card_html = f"""
                    <div style='
                        background-color: white;
                        padding: 10px;
                        border-radius: 5px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        min-width: 200px;
                        border: 1px solid #ddd;
                    '>
                        <div style='
                            background-color: #3498db;
                            color: white;
                            padding: 5px;
                            border-radius: 3px;
                            margin-bottom: 8px;
                            font-weight: bold;
                            text-align: center;
                        '>
                            {row['facility_name']}
                        </div>
                        <div style='margin: 5px 0;'>
                            <span style='font-weight: bold;'>Total Cases:</span> 
                            <span style='float: right;'>{row['Total Cases']:,.0f}</span>
                        </div>
                        <div style='margin: 5px 0;'>
                            <span style='font-weight: bold;'>Monthly Avg:</span> 
                            <span style='float: right;'>{row['Average Cases']:.1f}</span>
                        </div>
                        <div style='margin: 5px 0;'>
                            <span style='font-weight: bold;'>Max Cases:</span> 
                            <span style='float: right;'>{row['Maximum Cases']:,.0f}</span>
                        </div>
                        <div style='
                            margin-top: 8px;
                            padding-top: 5px;
                            border-top: 1px solid #eee;
                            color: {card_color};
                            text-align: center;
                            font-weight: bold;
                        '>
                            {f"▲ {mom_growth:+.1f}%" if mom_growth >= 0 else f"▼ {mom_growth:.1f}%"}
                        </div>
                    </div>
                    """
                    
                    markers.append(
                        dl.Popup(
                            position=[lat, lon],
                            children=[html.Div([
                                html.Iframe(
                                    srcDoc=card_html,
                                    style={
                                        'border': 'none',
                                        'width': '220px',
                                        'height': '200px'
                                    }
                                )
                            ])],
                            closeButton=False,
                            className='custom-popup'
                        )
                    )
            
            # Create bar chart with growth indicators
            bar_fig = px.bar(
                agg_data,
                x='facility_name',
                y='Total Cases',
                title=f'Total Malaria Cases by Facility ({year_range[0]}-{year_range[1]})'
            )

            # Add arrows to bars based on growth
            for i, row in agg_data.iterrows():
                facility_data = district_data[district_data['facility_name'] == row['facility_name']]
                facility_monthly = facility_data.groupby(['Year', 'Month'])['Malaria_cases_OPD'].sum().reset_index()
                if len(facility_monthly) > 1:
                    last_month = facility_monthly.iloc[-1]['Malaria_cases_OPD']
                    prev_month = facility_monthly.iloc[-2]['Malaria_cases_OPD']
                    mom_growth = ((last_month - prev_month) / prev_month * 100) if prev_month != 0 else 0
                    
                    arrow_color = '#2ecc71' if mom_growth >= 0 else '#e74c3c'
                    arrow_symbol = '▲' if mom_growth >= 0 else '▼'
                    
                    bar_fig.add_annotation(
                        x=row['facility_name'],
                        y=row['Total Cases'],
                        text=arrow_symbol,
                        showarrow=False,
                        font=dict(size=20, color=arrow_color),
                        yshift=10
                    )

            # Update bar chart layout
            bar_fig.update_layout(
                showlegend=True,
                xaxis_tickangle=-45,
                margin=dict(b=100)
            )
            
            # Create trend chart
            monthly_data = district_data.groupby(['Year', 'Month'])['Malaria_cases_OPD'].sum().reset_index()
            monthly_data['Date'] = pd.to_datetime(monthly_data[['Year', 'Month']].assign(DAY=1))
            
            trend_fig = px.line(
                monthly_data,
                x='Date',
                y='Malaria_cases_OPD',
                title='Monthly Trend of Malaria Cases'
            )
            
            # Calculate summary statistics
            total_cases = district_data['Malaria_cases_OPD'].sum()
            avg_monthly = monthly_data['Malaria_cases_OPD'].mean()
            if len(monthly_data) >= 2:
                growth_rate = ((monthly_data['Malaria_cases_OPD'].iloc[-1] - 
                              monthly_data['Malaria_cases_OPD'].iloc[0]) / 
                              monthly_data['Malaria_cases_OPD'].iloc[0] * 100)
            else:
                growth_rate = 0
            
            # Create summary statistics cards
            summary_stats = [
                html.Div([
                    html.H4("Total Cases"),
                    html.H2(f"{total_cases:,.0f}")
                ], style={**card_style, 'backgroundColor': '#3498db', 'color': 'white'}),
                
                html.Div([
                    html.H4("Monthly Average"),
                    html.H2(f"{avg_monthly:,.0f}")
                ], style={**card_style, 'backgroundColor': '#2ecc71', 'color': 'white'}),
                
                html.Div([
                    html.H4("Period Growth"),
                    html.H2(f"{growth_rate:+.1f}%")
                ], style={**card_style, 'backgroundColor': '#9b59b6', 'color': 'white'})
            ]
            
            return (agg_data.to_dict('records'), columns, geojson_data, 
                    markers, bar_fig, trend_fig, summary_stats)
            
        except Exception as e:
            print(f"Callback error: {str(e)}")
            return [], [], {'type': 'FeatureCollection', 'features': []}, [], {}, {}, []

else:
    app.layout = html.Div([
        html.H1("Error Loading Data",
                style={'textAlign': 'center', 'color': 'red'}),
        html.P("Please check if your data files exist and are in the correct format.",
               style={'textAlign': 'center'})
    ])

if __name__ == '__main__':
    app.run_server(host="0.0.0.0", port=8000, debug=False)
