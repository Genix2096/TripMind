"""SYNTHETIC provider payloads for parser tests only. Never import from app code.

Shapes follow the official SerpApi / Geoapify / OpenWeather / Groq documentation; the values are
made up and say nothing about real flights, hotels, places or weather.
"""

FLIGHTS_OK = {
    "search_metadata": {"id": "sm1", "status": "Success", "google_flights_url": "https://example.test/gf"},
    "search_parameters": {"engine": "google_flights", "currency": "INR"},
    "best_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 08:00"},
                    "arrival_airport": {"name": "B Airport", "id": "BBB", "time": "2026-12-01 10:00"},
                    "duration": 120,
                    "airplane": "Test 100",
                    "airline": "TestAir",
                    "travel_class": "Economy",
                    "flight_number": "TA 1",
                    "overnight": False,
                    "extensions": ["Wi-Fi"],
                }
            ],
            "total_duration": 120,
            "price": 5400,
            "type": "Round trip",
            "carbon_emissions": {"this_flight": 90000},
            "departure_token": "tok-out-1",
        }
    ],
    "other_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 06:00"},
                    "arrival_airport": {"name": "C Airport", "id": "CCC", "time": "2026-12-01 08:00"},
                    "duration": 120,
                    "airline": "OtherAir",
                },
                {
                    "departure_airport": {"id": "CCC", "time": "2026-12-01 09:00"},
                    "arrival_airport": {"id": "BBB", "time": "not-a-time"},
                    "duration": 90,
                    "airline": "OtherAir",
                },
            ],
            "layovers": [{"duration": 60, "name": "C Airport", "id": "CCC"}],
            "total_duration": 270,
            # price intentionally missing
            "type": "Round trip",
        },
        "garbage-entry",
        {"flights": []},
    ],
    "price_insights": {"lowest_price": 5000},
}

FLIGHTS_WITH_DUPLICATES = {
    "search_metadata": {"id": "sm_dup", "status": "Success", "google_flights_url": "https://example.test/gf"},
    "search_parameters": {"engine": "google_flights", "currency": "INR"},
    "best_flights": [
        # Flight A
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 08:00"},
                    "arrival_airport": {"name": "B Airport", "id": "BBB", "time": "2026-12-01 10:00"},
                    "duration": 120,
                    "airline": "TestAir",
                    "flight_number": "TA 1",
                }
            ],
            "total_duration": 120,
            "price": 5400,
            "booking_token": "token_best_1",
        },
        # Flight B
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 10:00"},
                    "arrival_airport": {"name": "B Airport", "id": "BBB", "time": "2026-12-01 12:00"},
                    "duration": 120,
                    "airline": "SkyWay",
                    "flight_number": "SW 202",
                }
            ],
            "total_duration": 120,
            "price": 6200,
            "booking_token": "token_best_2",
        },
    ],
    "other_flights": [
        # Duplicate of Flight A (equivalent airline case/space, flight number space, same time, same price, different token)
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 08:00"},
                    "arrival_airport": {"name": "B Airport", "id": "BBB", "time": "2026-12-01 10:00"},
                    "duration": 120,
                    "airline": "testair ",
                    "flight_number": "TA1",
                }
            ],
            "total_duration": 120,
            "price": 5400.0,
            "booking_token": "token_other_dup_diff_token",
        },
        # Distinct Flight C: different departure time (12:00 vs 08:00)
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 12:00"},
                    "arrival_airport": {"name": "B Airport", "id": "BBB", "time": "2026-12-01 14:00"},
                    "duration": 120,
                    "airline": "TestAir",
                    "flight_number": "TA 1",
                }
            ],
            "total_duration": 120,
            "price": 5400,
            "booking_token": "token_c",
        },
        # Distinct Flight D: different flight number (TA 2 vs TA 1)
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 08:00"},
                    "arrival_airport": {"name": "B Airport", "id": "BBB", "time": "2026-12-01 10:00"},
                    "duration": 120,
                    "airline": "TestAir",
                    "flight_number": "TA 2",
                }
            ],
            "total_duration": 120,
            "price": 5400,
            "booking_token": "token_d",
        },
        # Distinct Flight E: different price (7000 vs 6200)
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 10:00"},
                    "arrival_airport": {"name": "B Airport", "id": "BBB", "time": "2026-12-01 12:00"},
                    "duration": 120,
                    "airline": "SkyWay",
                    "flight_number": "SW 202",
                }
            ],
            "total_duration": 120,
            "price": 7000,
            "booking_token": "token_e",
        },
        # Distinct Flight F: different airline (AeroFly vs TestAir/SkyWay)
        {
            "flights": [
                {
                    "departure_airport": {"name": "A Airport", "id": "AAA", "time": "2026-12-01 14:00"},
                    "arrival_airport": {"name": "B Airport", "id": "BBB", "time": "2026-12-01 16:00"},
                    "duration": 120,
                    "airline": "AeroFly",
                    "flight_number": "AF 300",
                }
            ],
            "total_duration": 120,
            "price": 4800,
            "booking_token": "token_f",
        },
    ],
}

HOTELS_OK = {
    "search_metadata": {"id": "hm1", "status": "Success"},
    "search_parameters": {"currency": "INR"},
    "serpapi_pagination": {"next_page_token": "next-1"},
    "properties": [
        {
            "type": "hotel",
            "name": "Test Resort",
            "property_token": "ptok1",
            "link": "https://example.test/resort",
            "gps_coordinates": {"latitude": 15.5, "longitude": 73.8},
            "check_in_time": "2:00 PM",
            "rate_per_night": {
                "lowest": "₹4,000", "extracted_lowest": 4000,
                "before_taxes_fees": "₹3,500", "extracted_before_taxes_fees": 3500,
            },
            "total_rate": {"lowest": "₹16,000", "extracted_lowest": 16000},
            "prices": [{"source": "Site", "num_guests": 2, "rate_per_night": {"extracted_lowest": 4100}}],
            "images": [{"thumbnail": "https://example.test/t.jpg", "original_image": "https://example.test/o.jpg"}],
            "overall_rating": 4.3,
            "reviews": 250,
            "extracted_hotel_class": 4,
            "amenities": ["Free Wi-Fi", "Pool"],
            "excluded_amenities": ["No airport shuttle"],
        },
        {
            "type": "hotel",
            "name": "Display Only Inn",
            "rate_per_night": {"lowest": "₹2,000"},
        },
        {"type": "hotel"},  # no name -> skipped
    ],
}

NO_RESULTS = {"error": "Google Flights hasn't returned any results for this query."}
HOTEL_NO_RESULTS = {"error": "Google Hotels hasn't returned any results for this query."}
PROVIDER_ERROR = {"error": "Invalid API key. Your API key should be here: https://serpapi.com/manage-api-key"}

PLACES_OK = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "name": "Test Fort",
                "place_id": "pid1",
                "formatted": "Test Fort, Test City",
                "city": "Test City",
                "lat": 15.4,
                "lon": 73.8,
                "categories": ["tourism.sights", "heritage"],
                "distance": 1234,
                "datasource": {"raw": {"opening_hours": "Mo-Su 09:00-17:00", "website": "https://example.test/fort"}},
            },
            "geometry": {"type": "Point", "coordinates": [73.8, 15.4]},
        },
        {
            "type": "Feature",
            "properties": {"formatted": "Nameless", "categories": ["beach"]},
            "geometry": {"type": "Point", "coordinates": [73.7, 15.3]},
        },
        {"type": "Feature", "properties": {"name": "No coords"}, "geometry": None},
    ],
}

GEOCODE_OK = {
    "results": [
        {"lat": 15.49, "lon": 73.83, "formatted": "Goa, India", "country": "India", "result_type": "state",
         "place_id": "g1", "rank": {"confidence": 0.9}}
    ]
}

ROUTE_OK = {
    "features": [
        {
            "properties": {
                "mode": "drive", "distance": 12000, "time": 1500,
                "legs": [{"distance": 12000, "time": 1500}],
            },
            "geometry": {"type": "MultiLineString", "coordinates": [[[73.8, 15.4], [73.9, 15.5], ["x", 1]]]},
        }
    ]
}

CURRENT_OK = {
    "id": 123, "name": "Testville", "dt": 1790000000,
    "main": {"temp": 29.5, "feels_like": 33.1, "humidity": 80},
    "weather": [{"main": "Clouds", "description": "scattered clouds"}],
    "wind": {"speed": 3.2}, "clouds": {"all": 40},
}


def forecast_payload(start_ts: int, blocks: int, tz: int = 19800) -> dict:
    return {
        "cod": "200",
        "city": {"name": "Testville", "timezone": tz},
        "list": [
            {
                "dt": start_ts + i * 10800,
                "main": {"temp": 28.0, "temp_min": 26.0, "temp_max": 30.0, "humidity": 70},
                "weather": [{"main": "Rain", "description": "light rain"}],
                "pop": 0.4,
                "rain": {"3h": 1.2},
            }
            for i in range(blocks)
        ],
    }


GROQ_OK = {
    "model": "test-model",
    "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": '{"origin": "MAA"}'}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}
GROQ_TOOL = {
    "choices": [
        {
            "finish_reason": "tool_calls",
            "message": {
                "content": None,
                "tool_calls": [{"id": "c1", "function": {"name": "search_flights", "arguments": '{"a": 1}'}}],
            },
        }
    ]
}

GOOGLE_MAPS_OK = {
    "search_metadata": {
        "id": "maps_meta_1",
        "status": "Success",
        "google_maps_url": "https://maps.google.com/test",
    },
    "search_parameters": {
        "engine": "google_maps",
        "type": "search",
        "q": "top attractions in Paris",
        "ll": "@48.8566,2.3522,14z",
    },
    "local_results": [
        {
            "position": 1,
            "title": "Eiffel Tower",
            "place_id": "ChIJLU7jZClu5kcR4PcOOO6pNm0",
            "data_id": "0x47e66e2964e34e2d:0x6d36a9ee380ef7e0",
            "gps_coordinates": {"latitude": 48.8584, "longitude": 2.2945},
            "rating": 4.7,
            "reviews": 350000,
            "types": ["Monument", "Tourist attraction"],
            "address": "Champ de Mars, 5 Av. Anatole France, 75007 Paris, France",
            "open_state": "Open ⋅ Closes 11:45 PM",
            "hours": "Open ⋅ Closes 11:45 PM",
            "website": "https://www.toureiffel.paris/en",
            "phone": "+33 892 70 12 39",
            "reviews_link": "https://example.test/reviews/eiffel",
        },
        {
            "position": 2,
            "title": "Louvre Museum",
            "place_id": "ChIJD7fiBh9u5kcRYJSMaMOCCwQ",
            "gps_coordinates": {"latitude": 48.8606, "longitude": 2.3376},
            "rating": 4.8,
            "reviews": 280000,
            "type": "Art museum",
            "address": "Rue de Rivoli, 75001 Paris, France",
            "hours": "Open ⋅ Closes 6:00 PM",
            "website": "https://www.louvre.fr/en",
            "reviews_link": "https://example.test/reviews/louvre",
        },
        {
            "position": 3,
            "title": "Eiffel Tower duplicate",
            "place_id": "ChIJLU7jZClu5kcR4PcOOO6pNm0",
            "gps_coordinates": {"latitude": 48.8584, "longitude": 2.2945},
        },
        {
            "position": 4,
            "title": "Ghost Attraction",
            "place_id": "ghost_1",
        },
        {
            "position": 5,
            "place_id": "nameless_1",
            "gps_coordinates": {"latitude": 48.86, "longitude": 2.34},
        },
    ],
}

GOOGLE_MAPS_EMPTY = {
    "search_metadata": {"id": "maps_empty", "status": "Success"},
    "local_results": [],
}

GOOGLE_MAPS_NO_RESULTS = {
    "error": "Google Maps hasn't returned any results for this query.",
}

GOOGLE_MAPS_BAD_SHAPE = {
    "search_metadata": {"id": "maps_bad", "status": "Success"},
    "unexpected": True,
}

GOOGLE_MAPS_DUPLICATES = {
    "search_metadata": {"id": "maps_dup", "status": "Success"},
    "local_results": [
        {
            "title": "Central Park",
            "gps_coordinates": {"latitude": 40.7829, "longitude": -73.9654},
            "rating": 4.8,
            "reviews": 150000,
        },
        {
            "title": "central park  ",
            "gps_coordinates": {"latitude": 40.78289, "longitude": -73.96538},
            "rating": 4.8,
            "reviews": 150000,
        },
    ],
}

