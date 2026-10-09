import json
import logging
from pathlib import Path
from typing import Optional, Union
import pandas as pd

from src.ingestion.gtfs_loader import GTFSFeed

logger = logging.getLogger(__name__)


def generate_route_map(
    feed: GTFSFeed,
    route_identifier: str,
    output_path: Union[str, Path],
    trip_id: Optional[str] = None
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    routes = feed.routes
    # Search by route_id, route_short_name, exact route_long_name, or prefix
    matched_route = routes[
        (routes["route_id"] == str(route_identifier)) |
        (routes["route_short_name"].fillna("").astype(str) == str(route_identifier)) |
        (routes["route_long_name"].fillna("").astype(str).str.upper() == str(route_identifier).upper()) |
        (routes["route_long_name"].fillna("").astype(str).str.upper().str.startswith(str(route_identifier).upper()))
    ]

    if matched_route.empty:
        raise ValueError(f"Route identifier '{route_identifier}' not found in routes.txt.")

    route_row = matched_route.iloc[0]
    route_id = str(route_row["route_id"])
    route_short_name = str(route_row.get("route_short_name") or route_row.get("route_long_name") or route_id)
    route_long_name = str(route_row.get("route_long_name", route_short_name))

    trips = feed.get_route_trips(route_id)
    if trips.empty:
        raise ValueError(f"No trips found for route_id '{route_id}'.")

    if trip_id is None:
        st_counts = feed.stop_times[feed.stop_times["trip_id"].isin(trips["trip_id"])]
        if st_counts.empty:
            raise ValueError(f"No stop_times found for trips of route '{route_id}'.")
        longest_trip_id = st_counts["trip_id"].value_counts().index[0]
        trip_id = longest_trip_id

    trip_stops = feed.get_trip_stops(trip_id)
    if trip_stops.empty:
        raise ValueError(f"No stops mapped for trip_id '{trip_id}'.")

    valid_stops = trip_stops.dropna(subset=["stop_lat", "stop_lon"])
    stops_data = []
    lat_lngs = []

    for _, row in valid_stops.iterrows():
        lat = float(row["stop_lat"])
        lon = float(row["stop_lon"])
        seq = int(row["stop_sequence"])
        name = str(row.get("stop_name", f"Stop {seq}"))
        stop_id = str(row["stop_id"])
        arr_time = str(row.get("arrival_time", ""))

        stops_data.append({
            "stop_id": stop_id,
            "stop_name": name,
            "sequence": seq,
            "lat": lat,
            "lon": lon,
            "arrival_time": arr_time
        })
        lat_lngs.append([lat, lon])

    center_lat = sum(s["lat"] for s in stops_data) / len(stops_data)
    center_lon = sum(s["lon"] for s in stops_data) / len(stops_data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Route {route_short_name} - Transit Network Visualization</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f8fafc;
            color: #1e293b;
        }}
        #header {{
            padding: 14px 24px;
            background: #0f172a;
            color: #f8fafc;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        #header h1 {{
            margin: 0;
            font-size: 1.15rem;
            font-weight: 600;
        }}
        #header p {{
            margin: 2px 0 0 0;
            font-size: 0.85rem;
            color: #94a3b8;
        }}
        #stats {{
            font-size: 0.85rem;
            color: #cbd5e1;
        }}
        #container {{
            display: flex;
            height: calc(100vh - 65px);
        }}
        #map {{
            flex: 1;
            height: 100%;
        }}
        #sidebar {{
            width: 340px;
            background: #ffffff;
            border-left: 1px solid #e2e8f0;
            overflow-y: auto;
            padding: 16px;
            box-sizing: border-box;
        }}
        .stop-item {{
            padding: 10px;
            margin-bottom: 6px;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .stop-item:hover {{
            background: #f1f5f9;
        }}
        .stop-badge {{
            display: inline-block;
            background: #2563eb;
            color: #ffffff;
            font-size: 0.75rem;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            margin-right: 8px;
        }}
        .stop-name {{
            font-size: 0.9rem;
            font-weight: 500;
        }}
        .stop-sub {{
            font-size: 0.75rem;
            color: #64748b;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <div id="header">
        <div>
            <h1>Route {route_short_name}: {route_long_name}</h1>
            <p>Trip ID: {trip_id} | Route ID: {route_id}</p>
        </div>
        <div id="stats">
            Total Stops: <strong>{len(stops_data)}</strong>
        </div>
    </div>
    <div id="container">
        <div id="map"></div>
        <div id="sidebar">
            <h3 style="margin-top: 0; font-size: 1rem;">Stop Sequence</h3>
            <div id="stop-list"></div>
        </div>
    </div>

    <script>
        const stops = {json.dumps(stops_data)};
        const latLngs = {json.dumps(lat_lngs)};

        const map = L.map('map').setView([{center_lat}, {center_lon}], 12);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);

        const routeLine = L.polyline(latLngs, {{
            color: '#2563eb',
            weight: 4,
            opacity: 0.8
        }}).addTo(map);

        map.fitBounds(routeLine.getBounds(), {{ padding: [30, 30] }});

        const markers = [];
        const listContainer = document.getElementById('stop-list');

        stops.forEach((stop, idx) => {{
            const isTerminal = (idx === 0 || idx === stops.length - 1);
            const markerColor = idx === 0 ? '#16a34a' : (idx === stops.length - 1 ? '#dc2626' : '#2563eb');
            
            const marker = L.circleMarker([stop.lat, stop.lon], {{
                radius: isTerminal ? 8 : 5,
                fillColor: markerColor,
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9
            }}).addTo(map);

            marker.bindPopup(`
                <strong>#${{stop.sequence}} ${{stop.stop_name}}</strong><br/>
                Stop ID: ${{stop.stop_id}}<br/>
                Scheduled: ${{stop.arrival_time || 'N/A'}}
            `);

            markers.push(marker);

            const item = document.createElement('div');
            item.className = 'stop-item';
            item.innerHTML = `
                <div>
                    <span class="stop-badge" style="background:${{markerColor}}">${{stop.sequence}}</span>
                    <span class="stop-name">${{stop.stop_name}}</span>
                </div>
                <div class="stop-sub">Stop ID: ${{stop.stop_id}} | Arr: ${{stop.arrival_time || 'N/A'}}</div>
            `;
            item.onclick = () => {{
                map.flyTo([stop.lat, stop.lon], 15);
                marker.openPopup();
            }};
            listContainer.appendChild(item);
        }});
    </script>
</body>
</html>"""

    output_path.write_text(html_content, encoding="utf-8")
    logger.info("Route map written to: %s", output_path)
    return output_path
