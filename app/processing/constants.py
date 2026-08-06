"""Domain constants: document type mappings, source domains and iType sizing rules.

The values here are contractual. Output filenames and image dimensions produced
by the engine depend directly on them, so they must not be changed casually.
"""

from __future__ import annotations

OPERATION_MODE_RENAME_ONLY = 1
OPERATION_MODE_RESIZE = 2

PROPERTY_TYPE_MVC = "MVC"
PROPERTY_TYPE_LEGACY = "LEGACY"

PRIMARY_DOMAIN = "www.rentcafe.com"
FALLBACK_DOMAINS = ("cdngeneral.rentcafe.com", "cdngeneralcf.rentcafe.com")

DOWNLOAD_TIMEOUT_SECONDS = 15

# Fraction trimmed from the top and the bottom of a portrait image before it is
# scaled down, so the subject is not squeezed into a landscape target box.
VERTICAL_CROP_RATIO = 0.15

# Doc. Type values as they appear in the source export, mapped to the
# abbreviation appended to generated filenames.
DOC_TYPE_MAPPING = {
    "PHOTO GALLERY": "PG",
    "FLASH GALLERY": "Flash",
    "FLASH/ HOMEPAGE SLIDER": "Flash",
    "PROPERTY LOGO": "log",
    "PROPERTY LOGO - EMAIL": "log",
    "PROPERTY LOGO - BROCHURE": "log",
    "ILS PROPERTY LOGO": "log",
    "CONTENT EDITOR": "CE",
    "COMMUNITY THUMBNAIL": "thumbnail",
    "FLOOR PLAN": "FP",
    "FLOORPLAN": "FP",
    "SITE PLAN": "SP",
    "UNIT VIDEO": "UV",
    "VIRTUAL TOUR": "VT",
    "AMENITY": "AmenityImage",
    "AMENITY IMAGES": "AmenityImage",
    "BACKGROUND": "BG",
    "BACKGROUND IMAGE": "BG",
    "TEMPLATE IMAGE": "Template",
    "TEMPLATE IMAGES": "Template",
    "BANNER": "Banner",
    "BANNER IMAGE": "Banner",
    "THEME LEFT IMAGE": "LeftThemeImage",
    "THEME RIGHT IMAGE": "RightThemeImage",
    "CORP SEARCH RESULTS BANNER": "Banner",
    "FOOTER IMAGE": "Footer",
    "FAVICON IMAGE": "Favicon",
    "ITEMS OF INTEREST": "IOI",
    "EMAIL ATTACHMENT": "EmailAttach",
    "UNIT IMAGE": "UnitImage",
    "RESIDENT APP LOGO IMAGE": "AppLogo",
    "BUILDING SVG MAP": "BuildingMap",
    "FLOOR SVG MAP": "FloorMap",
}

UNKNOWN_DOC_TYPE_ABBREVIATION = "XX"

# Spellings that already convey the doc type. If the original filename contains
# any of them the abbreviation is not appended a second time.
SHORTHAND_CHECK = {
    "PG": ["pg", "photogallery", "photogallary", "photo gallary", "photo gallery"],
    "Flash": ["flashgallery", "flash"],
    "log": ["propertylogo", "logo", "log"],
    "CE": ["contenteditor", "ce"],
    "thumbnail": ["communitythumbnail", "thumbnail", "thumb"],
    "FP": ["floorplan", "fp"],
    "SP": ["siteplan", "sp"],
    "AmenityImage": ["amenityimages", "amenityimage", "amenityimg"],
    "BG": ["backgroundimage", "background", "bg"],
    "Template": ["templateimage", "template"],
    "Banner": ["bannerimage", "banner"],
    "LeftThemeImage": ["leftthemeimage", "lefttheme"],
    "RightThemeImage": ["rightthemeimage", "righttheme"],
    "Footer": ["footerimage", "footer"],
    "Favicon": ["faviconimage", "favicon"],
    "IOI": ["itemsofinterest", "ioi"],
    "EmailAttach": ["emailattachment", "emailattach"],
    "UnitImage": ["unitimage"],
    "AppLogo": ["residentapplogo", "applogo"],
    "BuildingMap": ["buildingsvgmap", "buildingmap", "buildingsvg"],
    "FloorMap": ["floorsvgmap", "floormap", "floorsvg"],
}

# An effectively unbounded edge, used where only one dimension is constrained.
UNBOUNDED = 99999

# iType values whose target box does not depend on the property type.
_SHARED_TARGET_BOXES = {
    2: (UNBOUNDED, 480),
    5: (500, 350),
    6: (350, UNBOUNDED),
    40: (UNBOUNDED, 1000),
}

_LEGACY_TARGET_BOXES = {
    120: (670, 480),
    1: (1024, 768),
}

_MVC_TARGET_BOXES = dict.fromkeys([1, 120, 12, 10, 4, 13, 14, 15, 28], (2560, 1707))


def get_target_box(itype: object, property_type: str) -> tuple[int, int] | None:
    """Return the (width, height) box an image of this iType must fit inside.

    Returns None when the iType has no rule, in which case the image is left at
    its original size.
    """
    try:
        itype_value = int(float(str(itype).strip()))
    except (TypeError, ValueError):
        return None

    if itype_value in _SHARED_TARGET_BOXES:
        return _SHARED_TARGET_BOXES[itype_value]

    if str(property_type).strip().upper() == PROPERTY_TYPE_LEGACY:
        return _LEGACY_TARGET_BOXES.get(itype_value)
    return _MVC_TARGET_BOXES.get(itype_value)
