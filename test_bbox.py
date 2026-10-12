import asyncio
import aiohttp
from typing import List, Dict, Any

CITY_BBOXES = {
    "US": [
        ("New York", "40.50,-74.25,40.90,-73.70"),
        ("Los Angeles", "33.70,-118.67,34.33,-118.15"),
        ("Chicago", "41.64,-87.94,42.02,-87.52"),
        ("Houston", "29.50,-95.80,30.15,-95.00"),
        ("Austin", "30.15,-97.95,30.50,-97.55"),
        ("Dallas", "32.60,-97.00,33.00,-96.50"),
        ("Miami", "25.70,-80.35,25.90,-80.10"),
    ],
    "UK": [
        ("London", "51.30,-0.50,51.70,0.30"),
        ("Manchester", "53.35,-2.35,53.60,-2.10"),
        ("Birmingham", "52.38,-2.02,52.55,-1.75"),
    ],
    "CA": [
        ("Toronto", "43.58,-79.64,43.85,-79.11"),
        ("Vancouver", "49.19,-123.27,49.32,-123.02"),
    ],
    "AU": [
        ("Sydney", "-34.05,150.95,-33.65,151.35"),
        ("Melbourne", "-37.95,144.80,-37.65,145.20"),
    ]
}

async def test_bbox_osm():
    city, bbox = CITY_BBOXES["US"][4] # Austin
    keyword = "plumber"
    
    ql = f"""
    [out:json][timeout:10];
    (
      node["craft"~"plumber",i]({bbox});
      node["name"~"plumb",i]({bbox});
      way["name"~"plumb",i]({bbox});
      node["shop"~"plumber",i]({bbox});
    );
    out center 15;
    """
    
    url = "https://overpass-api.de/api/interpreter"
    headers = {"User-Agent": "LeadScoutBot/1.0 (contact: akdamdigitals@gmail.com)"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url, data={"data": ql}, timeout=15) as resp:
            print(f"OSM BBox Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                elements = data.get("elements", [])
                print(f"Found {len(elements)} businesses in {city} via BBox!")
                for el in elements[:5]:
                    tags = el.get("tags", {})
                    print(f" • {tags.get('name')} | Phone: {tags.get('phone')} | Website: {tags.get('website')}")

if __name__ == "__main__":
    asyncio.run(test_bbox_osm())
