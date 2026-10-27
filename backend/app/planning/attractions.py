"""Attraction preference extraction, relevance scoring, and package allocation.

Pure Python logic: grounded strictly in actual provider places data.
No fake attractions, opening hours, or ratings are ever invented.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.models.common import Coordinate
from app.models.day_plan import Activity, DayPlan
from app.models.geo import Place
from app.models.trip import (
    AttractionPreferenceSource,
    PacePreferenceSource,
    StructuredAttractionPreferences,
    StructuredTripPace,
    TripPace,
    TripState,
)

logger = logging.getLogger("app.planning.attractions")

# ---------------------------------------------------------------------------
# 1. Canonical Taxonomies & Keywords
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoryTaxonomy:
    key: str
    display_name: str
    keywords: tuple[str, ...]
    google_types: tuple[str, ...]
    recommended_search_tags: tuple[str, ...]
    is_regional: bool = False  # E.g. wildlife/national parks may be further from city center


TAXONOMY: dict[str, CategoryTaxonomy] = {
    "heritage": CategoryTaxonomy(
        key="heritage",
        display_name="Historical Architecture & Heritage",
        keywords=(
            "heritage", "historic", "historical", "architecture", "old architecture",
            "monument", "fort", "palace", "castle", "ruins", "ancient", "unesco",
            "archaeological", "memorial", "tomb", "citadel", "historic building",
        ),
        google_types=(
            "historical_landmark", "monument", "tourist_attraction", "castle",
            "place_of_worship", "historic_site",
        ),
        recommended_search_tags=("tourism.sights", "heritage", "monument", "historical_landmark"),
    ),
    "wildlife": CategoryTaxonomy(
        key="wildlife",
        display_name="Wildlife & Sanctuaries",
        keywords=(
            "wildlife", "sanctuary", "national park", "safari", "reserve", "animals",
            "zoo", "bird sanctuary", "tiger reserve", "wildlife sanctuary", "fauna",
            "biodiversity", "jungle", "safaris", "nature reserve",
        ),
        google_types=(
            "national_park", "zoo", "aquarium", "wildlife_park", "wildlife_refuge",
        ),
        recommended_search_tags=("nature_reserve", "wildlife", "leisure.park", "tourism.attraction"),
        is_regional=True,
    ),
    "nature": CategoryTaxonomy(
        key="nature",
        display_name="Nature & Scenic Landscapes",
        keywords=(
            "nature", "forest", "lake", "waterfall", "mountain", "hill", "valley",
            "garden", "botanical garden", "park", "scenic", "landscape", "outdoors",
            "river", "woods", "flora",
        ),
        google_types=(
            "park", "natural_feature", "campground", "hiking_area", "botanical_garden",
        ),
        recommended_search_tags=("leisure.park", "natural", "tourism.attraction", "tourism.sights"),
    ),
    "beaches": CategoryTaxonomy(
        key="beaches",
        display_name="Beaches & Coastal",
        keywords=(
            "beach", "coastal", "coast", "sea", "ocean", "island", "cove",
            "shoreline", "seaside", "watersports", "surf",
        ),
        google_types=(
            "beach", "natural_feature",
        ),
        recommended_search_tags=("beach", "coastal", "tourism.sights", "natural"),
    ),
    "museums": CategoryTaxonomy(
        key="museums",
        display_name="Museums, Art & Culture",
        keywords=(
            "museum", "art", "gallery", "exhibit", "cultural", "sculpture",
            "memorial", "heritage center", "painting", "fine arts", "history museum",
        ),
        google_types=(
            "museum", "art_gallery", "cultural_center",
        ),
        recommended_search_tags=("entertainment.museum", "entertainment.culture", "tourism.sights"),
    ),
    "food": CategoryTaxonomy(
        key="food",
        display_name="Food & Local Cuisine",
        keywords=(
            "food", "cuisine", "culinary", "street food", "food market", "dining",
            "local delicacies", "gourmet", "tasting", "wine", "brewery", "eat",
        ),
        google_types=(
            "restaurant", "food", "cafe", "market",
        ),
        recommended_search_tags=("catering.restaurant", "food_market", "tourism.attraction"),
    ),
    "shopping": CategoryTaxonomy(
        key="shopping",
        display_name="Shopping & Local Markets",
        keywords=(
            "shopping", "market", "bazaar", "souk", "handicrafts", "mall",
            "flea market", "artisan", "textiles", "antique",
        ),
        google_types=(
            "market", "shopping_mall", "store", "department_store",
        ),
        recommended_search_tags=("commercial.shopping_mall", "commercial.marketplace", "tourism.attraction"),
    ),
    "adventure": CategoryTaxonomy(
        key="adventure",
        display_name="Adventure & Outdoor Activities",
        keywords=(
            "adventure", "trekking", "hiking", "kayaking", "diving", "snorkeling",
            "camping", "rafting", "climbing", "zipline", "sports", "thrill",
        ),
        google_types=(
            "hiking_area", "campground", "amusement_center",
        ),
        recommended_search_tags=("sport", "hiking_area", "tourism.attraction"),
    ),
    "religious": CategoryTaxonomy(
        key="religious",
        display_name="Religious & Spiritual Sites",
        keywords=(
            "temple", "church", "cathedral", "mosque", "shrine", "monastery",
            "spiritual", "ashram", "gurudwara", "pilgrimage", "synagogue", "pagoda",
        ),
        google_types=(
            "place_of_worship", "church", "hindu_temple", "mosque", "synagogue",
        ),
        recommended_search_tags=("heritage", "place_of_worship", "tourism.sights"),
    ),
    "family": CategoryTaxonomy(
        key="family",
        display_name="Family-Friendly Attractions",
        keywords=(
            "family", "kids", "children", "theme park", "amusement park", "water park",
            "aquarium", "interactive",
        ),
        google_types=(
            "amusement_park", "water_park", "theme_park", "aquarium",
        ),
        recommended_search_tags=("entertainment", "amusement_park", "tourism.attraction"),
    ),
    "nightlife": CategoryTaxonomy(
        key="nightlife",
        display_name="Nightlife & Entertainment",
        keywords=(
            "nightlife", "entertainment", "club", "bar", "pub", "live music",
            "shows", "lounge", "theater", "comedy",
        ),
        google_types=(
            "bar", "night_club", "movie_theater",
        ),
        recommended_search_tags=("entertainment", "nightlife", "tourism.attraction"),
    ),
    "photography": CategoryTaxonomy(
        key="photography",
        display_name="Photography & Scenic Viewpoints",
        keywords=(
            "photography", "viewpoint", "lookout", "panorama", "sunset point",
            "skyline", "photo spot", "scenic view", "observation deck",
        ),
        google_types=(
            "observation_deck", "tourist_attraction", "natural_feature",
        ),
        recommended_search_tags=("tourism.sights", "natural", "tourism.attraction"),
    ),
}

# ---------------------------------------------------------------------------
# 2. Preference Extraction & Normalization
# ---------------------------------------------------------------------------

_EXPLICIT_INTEREST_PATTERNS = [
    re.compile(r"\b(?:i\s+like|i\s+love|interested\s+in|focus\s+on|focused\s+on|prefer|preference\s+for|keen\s+on|enjoy|want\s+to\s+see|looking\s+for)\s+([a-zA-Z\s,–—-]+?)(?:\.|$|,|and\s+also)", re.IGNORECASE),
    re.compile(r"\b(?:trip|vacation|holiday|tour)\s+(?:focused\s+on|centered\s+around|for)\s+([a-zA-Z\s,–—-]+?)(?:\.|$|,)", re.IGNORECASE),
]


def extract_attraction_preferences(ts: TripState) -> StructuredAttractionPreferences:
    """Extract and normalize structured attraction preferences.

    Deterministic logic ensures:
    1. Explicit interests from LLM or raw request are categorized into the taxonomy.
    2. Primary vs secondary interests are distinguished.
    3. User's original phrasing is preserved.
    4. Destination-only requests with no interest mentions default to balanced mode.
    """
    raw_text = ts.raw_request or ""
    current_prefs = ts.preferences.attraction_preferences if hasattr(ts.preferences, "attraction_preferences") else None
    existing_interests = list(ts.preferences.interests or [])

    # Collect candidate phrases from LLM's existing_interests or raw text extraction
    found_taxa: list[str] = []
    raw_phrases: list[str] = []

    # Check if LLM already populated attraction_preferences with explicit source
    if current_prefs and current_prefs.preference_source == AttractionPreferenceSource.USER_EXPLICIT:
        for p in current_prefs.primary_interests:
            tax = _match_taxonomy_key(p)
            if tax and tax not in found_taxa:
                found_taxa.append(tax)
        for s in current_prefs.secondary_interests:
            tax = _match_taxonomy_key(s)
            if tax and tax not in found_taxa:
                found_taxa.append(tax)
        raw_phrases.extend(current_prefs.raw_interest_phrases or [])

    # Check preferences.interests from LLM
    for item in existing_interests:
        tax = _match_taxonomy_key(item)
        if tax and tax not in found_taxa:
            found_taxa.append(tax)
        if item.strip() and item.strip() not in raw_phrases:
            raw_phrases.append(item.strip())

    # Deterministic scan of raw_request to catch explicit statements if LLM missed them
    # or to verify explicit source
    explicit_user_signals = False
    for pat in _EXPLICIT_INTEREST_PATTERNS:
        for match in pat.finditer(raw_text):
            phrase = match.group(1).strip()
            if len(phrase) >= 3 and len(phrase) <= 100:
                explicit_user_signals = True
                if phrase not in raw_phrases:
                    raw_phrases.append(phrase)
                for tax_key in _scan_text_for_taxa(phrase):
                    if tax_key not in found_taxa:
                        found_taxa.append(tax_key)

    # Determine if preferences were explicitly stated by user
    is_explicit = bool(found_taxa) and (explicit_user_signals or bool(existing_interests))

    if not is_explicit:
        # User specified no attraction interests -> Default balanced mode
        sp = StructuredAttractionPreferences(
            primary_interests=[],
            secondary_interests=[],
            preference_source=AttractionPreferenceSource.DEFAULT_BALANCED,
            raw_interest_phrases=[],
            summary_label="Balanced selection of popular local attractions",
        )
        ts.preferences.attraction_preferences = sp
        return sp

    # Structure into primary and secondary
    primary_keys = found_taxa[:2]
    secondary_keys = found_taxa[2:5]

    primary_labels = [TAXONOMY[k].display_name for k in primary_keys if k in TAXONOMY]
    secondary_labels = [TAXONOMY[k].display_name for k in secondary_keys if k in TAXONOMY]

    display_parts = [TAXONOMY[k].display_name.split("&")[0].strip() for k in primary_keys if k in TAXONOMY]
    summary_label = f"Your interests: {', '.join(display_parts)}" if display_parts else "Balanced selection of popular local attractions"

    sp = StructuredAttractionPreferences(
        primary_interests=primary_labels,
        secondary_interests=secondary_labels,
        preference_source=AttractionPreferenceSource.USER_EXPLICIT,
        raw_interest_phrases=raw_phrases[:10],
        summary_label=summary_label,
    )
    ts.preferences.attraction_preferences = sp
    # Sync ts.preferences.interests for backwards compatibility
    ts.preferences.interests = primary_labels + secondary_labels
    return sp


# ---------------------------------------------------------------------------
# 2b. Trip Pace Extraction & Conflict Resolution
# ---------------------------------------------------------------------------

_RUSHED_PATTERNS = [
    re.compile(r"\b(?:visit|see|cover)\s+(?:as\s+many\s+(?:places|attractions|sights)\s+as\s+possible|more\s+attractions|everything)\b", re.IGNORECASE),
    re.compile(r"\b(?:packed|busy|fast-paced|rushed|action-packed|high-density|intensive)\s+(?:itinerary|schedule|trip|pace|holiday|vacation)\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:want|prefer)\s+a\s+(?:packed|busy|rushed|fast)\b", re.IGNORECASE),
    re.compile(r"\bdon't\s+mind\s+a\s+busy\s+schedule\b", re.IGNORECASE),
    re.compile(r"\bcover\s+more\s+attractions\s+every\s+day\b", re.IGNORECASE),
    re.compile(r"\bpace\s*:\s*(?:rushed|packed|fast)\b", re.IGNORECASE),
    re.compile(r"\b(?:as\s+much\s+as\s+possible|pack\s+in\s+as\s+much|see\s+as\s+much\s+as\s+possible)\b", re.IGNORECASE),
]

_SLOW_PATTERNS = [
    re.compile(r"\b(?:relaxed|slow|leisurely|unhurried|chill|laid-back|easygoing)\s+(?:vacation|trip|itinerary|schedule|pace|holiday)\b", re.IGNORECASE),
    re.compile(r"\btake\s+it\s+slow(?:ly)?\b", re.IGNORECASE),
    re.compile(r"\bspend\s+more\s+time\s+at\s+each\s+(?:place|attraction|site|spot)\b", re.IGNORECASE),
    re.compile(r"\bleave\s+plenty\s+of\s+free\s+time\b", re.IGNORECASE),
    re.compile(r"\b(?:lots|plenty)\s+of\s+(?:free\s+time|downtime|rest)\b", re.IGNORECASE),
    re.compile(r"\bpace\s*:\s*(?:slow|relaxed|leisurely)\b", re.IGNORECASE),
    re.compile(r"\b(?:not\s+too\s+rushed|no\s+rush|without\s+rushing|relaxed\s+pace)\b", re.IGNORECASE),
]

_BALANCED_PATTERNS = [
    re.compile(r"\b(?:mix|balance)\s+of\s+sightseeing\s+and\s+(?:relaxation|free\s+time|rest)\b", re.IGNORECASE),
    re.compile(r"\bkeep\s+the\s+schedule\s+comfortable\b", re.IGNORECASE),
    re.compile(r"\b(?:balanced|comfortable|moderate)\s+(?:itinerary|schedule|pace|trip)\b", re.IGNORECASE),
    re.compile(r"\bpace\s*:\s*(?:balanced|moderate|medium)\b", re.IGNORECASE),
]


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two coordinates on Earth."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2) + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 1)


def extract_trip_pace(ts: TripState) -> StructuredTripPace:
    """Extract and normalize structured trip pacing preference.

    Deterministic logic ensures:
    1. Explicit natural language expressions are recognized (RUSHED, BALANCED, SLOW).
    2. Does NOT infer RUSHED merely because the user lists many interests.
    3. Conflicting pace instructions are resolved conservatively to BALANCED and noted.
    4. Defaults to BALANCED when no clear pace is expressed.
    """
    current_pace_pref = getattr(ts.preferences, "pace_preferences", None)
    if current_pace_pref and getattr(current_pace_pref, "preference_source", None) in (
        PacePreferenceSource.USER_EXPLICIT,
        PacePreferenceSource.EXPLICITLY_STATED,
    ) and getattr(current_pace_pref, "raw_pace_phrase", None):
        return current_pace_pref

    raw_text = ts.raw_request or ""

    rushed_match: str | None = None
    for pat in _RUSHED_PATTERNS:
        m = pat.search(raw_text)
        if m:
            rushed_match = m.group(0).strip()
            break

    slow_match: str | None = None
    for pat in _SLOW_PATTERNS:
        m = pat.search(raw_text)
        if m:
            slow_match = m.group(0).strip()
            break

    balanced_match: str | None = None
    for pat in _BALANCED_PATTERNS:
        m = pat.search(raw_text)
        if m:
            balanced_match = m.group(0).strip()
            break

    # Conflict check: User asked for BOTH rushed AND slow in explicit text
    if rushed_match and slow_match:
        conflict_msg = (
            f"Conflicting pace instructions detected in request: '{rushed_match}' vs '{slow_match}'. "
            "Defaulted conservatively to Balanced pace."
        )
        if conflict_msg not in ts.assumptions:
            ts.assumptions.append(conflict_msg)
        stp = StructuredTripPace(
            pace=TripPace.BALANCED,
            preference_source=PacePreferenceSource.DEFAULT_BALANCED,
            raw_pace_phrase=f"{rushed_match} / {slow_match}",
            summary_label="Balanced pace (conservative resolution)",
            description="A comfortable mix of sightseeing, breaks, and free time (resolved from conflicting pace inputs).",
        )
        ts.preferences.pace = TripPace.BALANCED
        ts.preferences.pace_preferences = stp
        return stp

    if rushed_match:
        stp = StructuredTripPace(
            pace=TripPace.RUSHED,
            preference_source=PacePreferenceSource.USER_EXPLICIT,
            raw_pace_phrase=rushed_match,
            summary_label="Rushed pace: packed sightseeing and maximum attractions",
            description="High-density sightseeing with more attractions per day and shorter transit buffers.",
        )
        ts.preferences.pace = TripPace.RUSHED
        ts.preferences.pace_preferences = stp
        return stp

    if slow_match:
        stp = StructuredTripPace(
            pace=TripPace.SLOW,
            preference_source=PacePreferenceSource.USER_EXPLICIT,
            raw_pace_phrase=slow_match,
            summary_label="Slow pace: relaxed schedule with more free time",
            description="Fewer attractions per day, longer visits, and plenty of unallocated free time.",
        )
        ts.preferences.pace = TripPace.SLOW
        ts.preferences.pace_preferences = stp
        return stp

    if balanced_match:
        stp = StructuredTripPace(
            pace=TripPace.BALANCED,
            preference_source=PacePreferenceSource.USER_EXPLICIT,
            raw_pace_phrase=balanced_match,
            summary_label="Balanced pace: sightseeing and relaxation",
            description="A comfortable mix of sightseeing, breaks, and free time.",
        )
        ts.preferences.pace = TripPace.BALANCED
        ts.preferences.pace_preferences = stp
        return stp

    # If no explicit regex match, check if ts.preferences.pace was set by LLM or API
    existing_pace = getattr(ts.preferences, "pace", None)
    if existing_pace == TripPace.RUSHED:
        stp = StructuredTripPace(
            pace=TripPace.RUSHED,
            preference_source=PacePreferenceSource.INFERRED,
            summary_label="Rushed pace: packed sightseeing and maximum attractions",
            description="High-density sightseeing with more attractions per day and shorter transit buffers.",
        )
        ts.preferences.pace_preferences = stp
        return stp

    if existing_pace == TripPace.SLOW:
        stp = StructuredTripPace(
            pace=TripPace.SLOW,
            preference_source=PacePreferenceSource.INFERRED,
            summary_label="Slow pace: relaxed schedule with more free time",
            description="Fewer attractions per day, longer visits, and plenty of unallocated free time.",
        )
        ts.preferences.pace_preferences = stp
        return stp

    # Default to BALANCED
    stp = StructuredTripPace(
        pace=TripPace.BALANCED,
        preference_source=PacePreferenceSource.DEFAULT_BALANCED,
        summary_label="Balanced pace: sightseeing and relaxation",
        description="A comfortable mix of sightseeing, breaks, and free time.",
    )
    ts.preferences.pace = TripPace.BALANCED
    ts.preferences.pace_preferences = stp
    return stp


def _match_taxonomy_key(text: str) -> str | None:
    low = text.lower().strip()
    for key, tax in TAXONOMY.items():
        if key in low or tax.display_name.lower() in low:
            return key
        for kw in tax.keywords:
            if kw in low:
                return key
    return None


def _scan_text_for_taxa(text: str) -> list[str]:
    low = text.lower()
    matches = []
    for key, tax in TAXONOMY.items():
        for kw in tax.keywords:
            if re.search(rf"\b{re.escape(kw)}\b", low):
                if key not in matches:
                    matches.append(key)
                break
    return matches


def recommend_search_categories(prefs: StructuredAttractionPreferences) -> list[str]:
    """Recommend Geoapify/Google Maps search category tokens for the Places search request."""
    if prefs.preference_source == AttractionPreferenceSource.DEFAULT_BALANCED or not prefs.primary_interests:
        return ["tourism.sights", "tourism.attraction", "heritage", "leisure.park", "entertainment.culture"]

    categories: list[str] = []
    for item in prefs.primary_interests + prefs.secondary_interests:
        key = _match_taxonomy_key(item)
        if key and key in TAXONOMY:
            for tag in TAXONOMY[key].recommended_search_tags:
                if tag not in categories:
                    categories.append(tag)
        if len(categories) >= 8:
            break

    if not categories:
        return ["tourism.sights", "tourism.attraction", "heritage", "leisure.park"]
    return categories[:10]


# ---------------------------------------------------------------------------
# 3. Attraction Scoring & Relevance Ranking
# ---------------------------------------------------------------------------

@dataclass
class ScoredPlace:
    place: Place
    relevance_score: float
    matched_taxa: list[str]
    match_reasons: list[str]
    is_explicit_match: bool


def _is_wildlife_match(place: Place) -> bool:
    """Strict wildlife verification: ordinary city parks are NOT counted as wildlife destinations."""
    combined = (
        f"{place.name or ''} {' '.join(place.categories)} {place.description or ''} {place.address or ''}"
    ).lower()
    wildlife_exclusive = {
        "wildlife", "sanctuary", "safari", "national park", "tiger reserve", "bird sanctuary",
        "zoo", "aquarium", "zoological", "fauna", "biodiversity", "reserve", "marine park",
    }
    has_wildlife = any(term in combined for term in wildlife_exclusive)
    # If it's solely a generic city park or garden without wildlife terms, it fails
    if not has_wildlife and ("park" in combined or "garden" in combined):
        return False
    return has_wildlife


def score_place(
    place: Place,
    prefs: StructuredAttractionPreferences,
    center: Coordinate | None = None,
) -> ScoredPlace:
    """Score a real provider attraction against user interests and quality signals.

    Explicit interests receive strictly higher priority than generic popularity.
    Trustworthy metadata (rating, reviews, opening hours, address) contributes to score.
    """
    score = 0.0
    matched_taxa: list[str] = []
    match_reasons: list[str] = []
    is_explicit_match = False

    place_categories = [c.lower().strip() for c in place.categories]
    place_name = (place.name or "").lower().strip()
    place_desc = (place.description or "").lower().strip()
    combined_text = f"{place_name} {' '.join(place_categories)} {place_desc}"

    primary_tax_keys = [_match_taxonomy_key(i) for i in prefs.primary_interests]
    primary_tax_keys = [k for k in primary_tax_keys if k is not None]
    secondary_tax_keys = [_match_taxonomy_key(i) for i in prefs.secondary_interests]
    secondary_tax_keys = [k for k in secondary_tax_keys if k is not None]

    if prefs.preference_source == AttractionPreferenceSource.USER_EXPLICIT and primary_tax_keys:
        # 1. Match Primary Interests
        for key in primary_tax_keys:
            tax = TAXONOMY[key]
            # Special check for wildlife
            if key == "wildlife":
                if _is_wildlife_match(place):
                    score += 85.0
                    is_explicit_match = True
                    matched_taxa.append(key)
                    match_reasons.append(f"Direct match: {tax.display_name}")
                continue

            # Check place categories (Google types)
            cat_match = any(gt in place_categories for gt in tax.google_types)
            kw_match = any(re.search(rf"\b{re.escape(kw)}\b", combined_text) for kw in tax.keywords)

            if cat_match and kw_match:
                score += 80.0
                is_explicit_match = True
                matched_taxa.append(key)
                match_reasons.append(f"Strong category & keyword match: {tax.display_name}")
            elif cat_match:
                score += 65.0
                is_explicit_match = True
                matched_taxa.append(key)
                match_reasons.append(f"Category match: {tax.display_name}")
            elif kw_match:
                score += 45.0
                is_explicit_match = True
                matched_taxa.append(key)
                match_reasons.append(f"Context match: {tax.display_name}")

        # 2. Match Secondary Interests
        for key in secondary_tax_keys:
            tax = TAXONOMY[key]
            if key == "wildlife":
                if _is_wildlife_match(place):
                    score += 35.0
                    is_explicit_match = True
                    matched_taxa.append(key)
                    match_reasons.append(f"Secondary match: {tax.display_name}")
                continue

            cat_match = any(gt in place_categories for gt in tax.google_types)
            kw_match = any(re.search(rf"\b{re.escape(kw)}\b", combined_text) for kw in tax.keywords)
            if cat_match or kw_match:
                score += 30.0
                matched_taxa.append(key)
                match_reasons.append(f"Secondary match: {tax.display_name}")

        # Baseline for places that do NOT match explicit interests when explicit interests were set
        if not is_explicit_match:
            score += 10.0
    else:
        # Default balanced mode: reward diversity across top attraction types
        score += 30.0
        for key, tax in TAXONOMY.items():
            if any(gt in place_categories for gt in tax.google_types):
                matched_taxa.append(key)
        if matched_taxa:
            match_reasons.append(f"Local sight ({', '.join(TAXONOMY[k].display_name.split('&')[0].strip() for k in matched_taxa[:2])})")

    # 3. Quality & Popularity Signals
    if place.rating is not None:
        if place.rating >= 4.5:
            score += 15.0
        elif place.rating >= 4.0:
            score += 10.0
        elif place.rating < 3.5:
            score -= 10.0

    if place.reviews_count is not None and place.reviews_count > 0:
        # Logarithmic scale for review count
        score += min(15.0, round(math.log10(place.reviews_count) * 3.5, 1))

    # 4. Verified Metadata Signals
    if place.opening_hours:
        score += 4.0
    if place.address:
        score += 3.0
    if place.website:
        score += 2.0

    # 5. Distance and Geographic Relevance
    dist = place.distance_from_center_m
    is_regional = any(TAXONOMY[k].is_regional for k in matched_taxa if k in TAXONOMY)
    if dist is not None:
        if not is_regional:
            if dist > 35_000:
                score -= 15.0
            elif dist > 20_000:
                score -= 8.0
            elif dist <= 8_000:
                score += 5.0
        else:
            # Regional venues (wildlife sanctuaries, national parks) naturally lie outside city centers
            if dist <= 60_000:
                score += 5.0

    return ScoredPlace(
        place=place,
        relevance_score=round(score, 2),
        matched_taxa=matched_taxa,
        match_reasons=match_reasons,
        is_explicit_match=is_explicit_match,
    )


def rank_attractions(
    places: list[Place],
    prefs: StructuredAttractionPreferences,
    center: Coordinate | None = None,
) -> list[ScoredPlace]:
    """Score, deduplicate and rank actual provider attractions by relevance."""
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    scored_list: list[ScoredPlace] = []

    for p in places:
        if not p.name or not p.name.strip():
            continue
        norm_name = p.name.strip().lower()
        if p.place_id and p.place_id in seen_ids:
            continue
        if norm_name in seen_names:
            continue

        if p.place_id:
            seen_ids.add(p.place_id)
        seen_names.add(norm_name)

        scored = score_place(p, prefs, center=center)
        scored_list.append(scored)

    # Sort descending by relevance score, tie-breaking by rating and review count
    scored_list.sort(
        key=lambda sp: (
            -sp.relevance_score,
            -(sp.place.rating or 0.0),
            -(sp.place.reviews_count or 0),
            sp.place.name or "",
        )
    )
    return scored_list


# ---------------------------------------------------------------------------
# 4. Meaningful Package Attraction Allocation
# ---------------------------------------------------------------------------

@dataclass
class PackageAttractionPlan:
    package_id: str
    theme_title: str
    theme_description: str
    allocated_places: list[Place]
    scored_candidates: list[ScoredPlace]
    variety_warning: str | None = None


def allocate_package_attractions(
    ranked_places: list[ScoredPlace],
    prefs: StructuredAttractionPreferences,
    calendar_days: int = 4,
    pace: TripPace = TripPace.BALANCED,
) -> dict[str, PackageAttractionPlan]:
    """Allocate distinct, theme-aligned attraction combinations across the 4 packages.

    Grounded strictly in actual provider results:
    - Never invents fake attractions.
    - If provider results have limited variety, reuses valid places and records an honest note.
    - All packages respect the user's explicit interests while providing different experiences.
    - Targets activity density matching the requested trip pace (RUSHED, BALANCED, SLOW).
    """
    total_places = len(ranked_places)
    has_explicit = prefs.preference_source == AttractionPreferenceSource.USER_EXPLICIT and prefs.primary_interests
    primary_tax_keys = [_match_taxonomy_key(i) for i in prefs.primary_interests]
    primary_tax_keys = [k for k in primary_tax_keys if k is not None]

    # Target number of attractions per package determined by requested pace
    if pace == TripPace.RUSHED:
        target_count = max(3, min(14, calendar_days * 3))
    elif pace == TripPace.SLOW:
        target_count = max(1, min(5, calendar_days * 1))
    else:  # BALANCED
        target_count = max(2, min(8, calendar_days * 2))

    # Define the 4 package focus styles
    if has_explicit:
        p_names = [TAXONOMY[k].display_name for k in primary_tax_keys if k in TAXONOMY]
        lead_name = p_names[0] if p_names else "Requested Interests"
        themes = [
            (
                "package-1",
                f"Iconic Highlights ({lead_name})",
                f"Emphasizes the most renowned and flagship landmarks aligned with {lead_name.lower()}.",
            ),
            (
                "package-2",
                f"In-Depth & Top-Rated ({lead_name})",
                f"Focuses on highly rated cultural, architectural, and deep exploration sites with top visitor ratings.",
            ),
            (
                "package-3",
                f"Scenic & Walkable ({lead_name})",
                f"Features open-air heritage quarters, scenic surroundings, and authentic local surroundings.",
            ),
            (
                "package-4",
                f"Curated & Signature ({lead_name})",
                f"Offers an expansive premium itinerary blending iconic landmarks with panoramic scenic viewpoints.",
            ),
        ]
    else:
        themes = [
            (
                "package-1",
                "Iconic City Highlights",
                "Balanced selection of must-see major landmarks and world-famous sights.",
            ),
            (
                "package-2",
                "Culture & Heritage Gems",
                "Focuses on top-rated historical monuments, museums, and rich cultural traditions.",
            ),
            (
                "package-3",
                "Nature & Scenic Discovery",
                "Features urban parks, scenic riverfronts/walkways, and relaxing open spaces.",
            ),
            (
                "package-4",
                "Signature Panoramic Experience",
                "Curated itinerary featuring signature city landmarks, observation decks, and viewpoints.",
            ),
        ]

    plans: dict[str, PackageAttractionPlan] = {}

    if total_places == 0:
        for pkg_id, title, desc in themes:
            plans[pkg_id] = PackageAttractionPlan(
                package_id=pkg_id,
                theme_title=title,
                theme_description=desc,
                allocated_places=[],
                scored_candidates=[],
                variety_warning="No attractions returned by provider.",
            )
        return plans

    # If results are very scarce (e.g. <= 3), share them honestly across all packages
    if total_places <= 3:
        shared_places = [sp.place for sp in ranked_places]
        warning = f"Attraction variety across packages is limited by available provider results (only {total_places} place(s) returned)."
        for pkg_id, title, desc in themes:
            plans[pkg_id] = PackageAttractionPlan(
                package_id=pkg_id,
                theme_title=title,
                theme_description=desc,
                allocated_places=list(shared_places),
                scored_candidates=list(ranked_places),
                variety_warning=warning,
            )
        return plans

    # If sufficient results exist, curate meaningfully distinct combinations
    explicit_matches = [sp for sp in ranked_places if sp.is_explicit_match] if has_explicit else ranked_places
    pool = explicit_matches if len(explicit_matches) >= 4 else ranked_places

    # Package 1: Top scores (Iconic / Flagship)
    p1_cands = pool[:target_count]

    # Package 2: Rotate candidates, emphasizing high rating
    p2_sorted = sorted(pool, key=lambda sp: (-(sp.place.rating or 0.0), -sp.relevance_score))
    p2_cands = []
    for sp in p2_sorted:
        if len(p2_cands) >= target_count:
            break
        p2_cands.append(sp)
    if len(p2_cands) < target_count:
        p2_cands = pool[:target_count]

    # Package 3: Walkable / Parks / Culture / Open-air sites
    def _is_walkable_or_scenic(sp: ScoredPlace) -> bool:
        cats = [c.lower() for c in sp.place.categories]
        name = (sp.place.name or "").lower()
        return any(k in cats or k in name for k in ("park", "garden", "market", "bazaar", "heritage", "monument", "natural_feature", "square"))

    scenic_walk = [sp for sp in pool if _is_walkable_or_scenic(sp)]
    remaining_pool = [sp for sp in pool if sp not in scenic_walk]
    p3_cands = (scenic_walk + remaining_pool)[:target_count]

    # Package 4: Curated Signature & Panoramic Viewpoints / Flagship
    def _is_signature_or_view(sp: ScoredPlace) -> bool:
        cats = [c.lower() for c in sp.place.categories]
        name = (sp.place.name or "").lower()
        return any(k in cats or k in name for k in ("viewpoint", "observation_deck", "palace", "fort", "museum", "tourist_attraction"))

    sig_views = [sp for sp in pool if _is_signature_or_view(sp)]
    p4_cands = (sig_views + [sp for sp in pool if sp not in sig_views])[:target_count]

    allocations = [p1_cands, p2_cands, p3_cands, p4_cands]

    # If combinations ended up identical due to small pool, inject available offset alternatives
    if total_places >= 5:
        for idx in range(1, 4):
            offset = idx % (total_places - target_count + 1)
            shifted = pool[offset : offset + target_count]
            if shifted and len(shifted) >= 2:
                allocations[idx] = shifted

    for i, (pkg_id, title, desc) in enumerate(themes):
        sel_cands = allocations[i]
        sel_places = [sp.place for sp in sel_cands]
        plans[pkg_id] = PackageAttractionPlan(
            package_id=pkg_id,
            theme_title=title,
            theme_description=desc,
            allocated_places=sel_places,
            scored_candidates=sel_cands,
        )

    return plans


# ---------------------------------------------------------------------------
# 5. Day-Wise Itinerary Activity Scheduling
# ---------------------------------------------------------------------------

def _place_to_activity(
    place: Place,
    time_slot: str,
    slot_label: str,
    duration: str = "2 to 3 hours",
) -> Activity:
    """Convert a normalized provider Place into a strictly source-backed DayPlan Activity."""
    desc_parts = []
    if place.categories:
        clean_cats = [c.replace("_", " ").title() for c in place.categories[:2]]
        desc_parts.append(f"{', '.join(clean_cats)}.")
    if place.rating:
        rev_text = f" ({place.reviews_count} reviews)" if place.reviews_count else ""
        desc_parts.append(f"Rated {place.rating}★ on Google Maps{rev_text}.")
    if place.description:
        desc_parts.append(place.description)

    desc = " ".join(desc_parts).strip() if desc_parts else "Verified point of interest."

    return Activity(
        name=f"{slot_label}: {place.name}",
        location=place.address or place.name,
        description=desc,
        time_window=place.opening_hours or time_slot,
        estimated_duration=duration,
        data_source="Google Maps (SerpApi)",
    )


def schedule_package_activities(
    days: list[DayPlan],
    plan: PackageAttractionPlan,
    destination: str,
    pace: TripPace = TripPace.BALANCED,
) -> list[DayPlan]:
    """Schedule the allocated attractions across the travel days according to trip pace.

    Preserves arrival/departure logistics, avoids duplication, ensures geographic proximity
    for packed days, respects unallocated downtime for relaxed days, and guarantees
    all activities reflect actual provider results without invention.
    """
    if not days or not plan.allocated_places:
        return days

    candidates = [p for p in plan.allocated_places if p and p.name and p.name.strip()]
    n_days = len(days)

    # Multi-day trip: intermediate days come first
    if n_days == 1:
        target_day_indices = [0]
    elif n_days == 2:
        target_day_indices = [0, 1]
    else:
        target_day_indices = list(range(1, n_days - 1))
        target_day_indices.append(0)
        target_day_indices.append(n_days - 1)

    # Slot configuration and daily activity limits based on pace
    if pace == TripPace.RUSHED:
        # High sightseeing density: tightly scheduled slots, shorter transit buffers
        slots = [
            ("Morning Exploration", "09:00 – 11:30", "1.5 to 2 hours"),
            ("Midday Discovery", "12:00 – 14:00", "1.5 to 2 hours"),
            ("Afternoon Sightseeing", "14:30 – 17:00", "2 hours"),
            ("Evening Atmosphere", "17:30 – 19:30", "1.5 to 2 hours"),
        ]

        def get_max_for_day(day_idx: int) -> int:
            is_first = (day_idx == 0 and n_days > 1)
            is_last = (day_idx == n_days - 1 and n_days > 1)
            if is_first:
                return 2  # Arrival afternoon & evening
            if is_last:
                return 1  # Departure morning
            return 3  # Intermediate days: up to 3 attractions

    elif pace == TripPace.SLOW:
        # Relaxed schedule: fewer activities per day, generous unallocated downtime
        slots = [
            ("Late Morning Leisure Visit", "10:30 – 13:30", "2.5 to 3.5 hours"),
            ("Late Afternoon Relaxed Stroll", "15:30 – 18:00", "2.5 hours"),
        ]

        def get_max_for_day(day_idx: int) -> int:
            is_first = (day_idx == 0 and n_days > 1)
            is_last = (day_idx == n_days - 1 and n_days > 1)
            if is_first or is_last:
                return 0  # Relaxed arrival and departure days without sightseeing rush
            return 1  # Intermediate days: 1 immersive visit with 2+ hours free buffer

    else:  # BALANCED
        # Moderate mix: practical combination of sightseeing and free time
        slots = [
            ("Morning Exploration", "09:30 – 12:30", "2 to 3 hours"),
            ("Afternoon Discovery", "14:00 – 17:00", "2 to 3 hours"),
            ("Evening Atmosphere", "17:30 – 19:30", "1.5 to 2 hours"),
        ]

        def get_max_for_day(day_idx: int) -> int:
            is_first = (day_idx == 0 and n_days > 1)
            is_last = (day_idx == n_days - 1 and n_days > 1)
            if is_first or is_last:
                return 1
            return 2

    def _pick_next_place(pool: list[Place], last_place: Place | None) -> Place | None:
        if not pool:
            return None
        # For rushed itineraries, prefer geographically proximate places to minimize transit time
        if pace == TripPace.RUSHED and last_place and last_place.coordinate:
            def _dist(p: Place) -> float:
                if not p.coordinate:
                    return float("inf")
                return _haversine_distance_m(
                    last_place.coordinate.lat, last_place.coordinate.lon,
                    p.coordinate.lat, p.coordinate.lon,
                )
            return min(pool, key=_dist)
        return pool[0]

    for day_idx in target_day_indices:
        if not candidates:
            break
        day = days[day_idx]

        is_first_day = (day_idx == 0 and n_days > 1)
        is_last_day = (day_idx == n_days - 1 and n_days > 1)
        max_for_day = get_max_for_day(day_idx)
        if max_for_day <= 0:
            continue

        existing_names = {a.name.lower() for a in day.activities}
        scheduled_today = 0
        last_place_today: Place | None = None

        for slot_label, slot_time, slot_duration in slots:
            if scheduled_today >= max_for_day or not candidates:
                break

            # Find next best candidate (geographically close if rushed)
            candidate_place = _pick_next_place(candidates, last_place_today)
            if not candidate_place:
                break

            if candidate_place.name and candidate_place.name.lower() in existing_names:
                candidates.remove(candidate_place)
                continue

            # Skip scheduling in morning on first day if flight arrival might conflict
            if is_first_day and "Morning" in slot_label:
                continue
            # Skip scheduling in afternoon/evening on last day if flight departure might conflict
            if is_last_day and ("Afternoon" in slot_label or "Evening" in slot_label):
                continue

            act = _place_to_activity(candidate_place, slot_time, slot_label, duration=slot_duration)
            day.activities.append(act)
            if candidate_place.name and candidate_place.name not in day.locations:
                day.locations.append(candidate_place.name)

            candidates.remove(candidate_place)
            last_place_today = candidate_place
            scheduled_today += 1

    return days
