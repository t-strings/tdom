# See https://developer.mozilla.org/en-US/docs/Glossary/Void_element
VOID_ELEMENTS = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]
)


CDATA_CONTENT_ELEMENTS = frozenset(["script", "style"])
RCDATA_CONTENT_ELEMENTS = frozenset(["textarea", "title"])
CONTENT_ELEMENTS = CDATA_CONTENT_ELEMENTS | RCDATA_CONTENT_ELEMENTS

SVG_TAG_FIX = {
    "altglyph": "altGlyph",
    "altglyphdef": "altGlyphDef",
    "altglyphitem": "altGlyphItem",
    "animatecolor": "animateColor",
    "animatemotion": "animateMotion",
    "animatetransform": "animateTransform",
    "clippath": "clipPath",
    "feblend": "feBlend",
    "fecolormatrix": "feColorMatrix",
    "fecomponenttransfer": "feComponentTransfer",
    "fecomposite": "feComposite",
    "feconvolvematrix": "feConvolveMatrix",
    "fediffuselighting": "feDiffuseLighting",
    "fedisplacementmap": "feDisplacementMap",
    "fedistantlight": "feDistantLight",
    "fedropshadow": "feDropShadow",
    "feflood": "feFlood",
    "fefunca": "feFuncA",
    "fefuncb": "feFuncB",
    "fefuncg": "feFuncG",
    "fefuncr": "feFuncR",
    "fegaussianblur": "feGaussianBlur",
    "feimage": "feImage",
    "femerge": "feMerge",
    "femergenode": "feMergeNode",
    "femorphology": "feMorphology",
    "feoffset": "feOffset",
    "fepointlight": "fePointLight",
    "fespecularlighting": "feSpecularLighting",
    "fespotlight": "feSpotLight",
    "fetile": "feTile",
    "feturbulence": "feTurbulence",
    "foreignobject": "foreignObject",
    "glyphref": "glyphRef",
    "lineargradient": "linearGradient",
    "radialgradient": "radialGradient",
    "textpath": "textPath",
}


SVG_ATTR_FIX = {
    "attributename": "attributeName",
    "attributetype": "attributeType",
    "basefrequency": "baseFrequency",
    "baseprofile": "baseProfile",
    "calcmode": "calcMode",
    "clippathunits": "clipPathUnits",
    "diffuseconstant": "diffuseConstant",
    "edgemode": "edgeMode",
    "filterunits": "filterUnits",
    "glyphref": "glyphRef",
    "gradienttransform": "gradientTransform",
    "gradientunits": "gradientUnits",
    "kernelmatrix": "kernelMatrix",
    "kernelunitlength": "kernelUnitLength",
    "keypoints": "keyPoints",
    "keysplines": "keySplines",
    "keytimes": "keyTimes",
    "lengthadjust": "lengthAdjust",
    "limitingconeangle": "limitingConeAngle",
    "markerheight": "markerHeight",
    "markerunits": "markerUnits",
    "markerwidth": "markerWidth",
    "maskcontentunits": "maskContentUnits",
    "maskunits": "maskUnits",
    "numoctaves": "numOctaves",
    "pathlength": "pathLength",
    "patterncontentunits": "patternContentUnits",
    "patterntransform": "patternTransform",
    "patternunits": "patternUnits",
    "pointsatx": "pointsAtX",
    "pointsaty": "pointsAtY",
    "pointsatz": "pointsAtZ",
    "preservealpha": "preserveAlpha",
    "preserveaspectratio": "preserveAspectRatio",
    "primitiveunits": "primitiveUnits",
    "refx": "refX",
    "refy": "refY",
    "repeatcount": "repeatCount",
    "repeatdur": "repeatDur",
    "requiredextensions": "requiredExtensions",
    "requiredfeatures": "requiredFeatures",
    "specularconstant": "specularConstant",
    "specularexponent": "specularExponent",
    "spreadmethod": "spreadMethod",
    "startoffset": "startOffset",
    "stddeviation": "stdDeviation",
    "stitchtiles": "stitchTiles",
    "surfacescale": "surfaceScale",
    "systemlanguage": "systemLanguage",
    "tablevalues": "tableValues",
    "targetx": "targetX",
    "targety": "targetY",
    "textlength": "textLength",
    "viewbox": "viewBox",
    "viewtarget": "viewTarget",
    "xchannelselector": "xChannelSelector",
    "ychannelselector": "yChannelSelector",
    "zoomandpan": "zoomAndPan",
}


# Used for fragments that do not have a tag
# to assume that text is inside this element.
DEFAULT_NORMAL_TEXT_ELEMENT = "div"


def make_invalid_attr_name_chars() -> set:
    """
    Create the set of invalid attribute name characters.

    @NOTE: See "HTML: The Living Standard" at https://html.spec.whatwg.org/dev/
    for source of character restrictions.
    """
    c0_control_chars = tuple(chr(i) for i in range(0x0000, 0x001F + 1))  # noqa: PIE808 match-spec
    control_chars = c0_control_chars + tuple(chr(i) for i in range(0x007F, 0x009F + 1))
    special_chars = tuple(
        chr(i)
        for i in [
            0x0020,  # SPACE
            0x0022,  # "
            0x0027,  # '
            0x003E,  # >
            0x002F,  # /
            0x003D,  # =
        ]
    )
    non_chars = tuple(
        chr(c)
        for c in (
            list(range(0xFDD0, 0xFDEF + 1))
            + [
                0xFFFE,
                0xFFFF,
                0x1FFFE,
                0x1FFFF,
                0x2FFFE,
                0x2FFFF,
                0x3FFFE,
                0x3FFFF,
                0x4FFFE,
                0x4FFFF,
                0x5FFFE,
                0x5FFFF,
                0x6FFFE,
                0x6FFFF,
                0x7FFFE,
                0x7FFFF,
                0x8FFFE,
                0x8FFFF,
                0x9FFFE,
                0x9FFFF,
                0xAFFFE,
                0xAFFFF,
                0xBFFFE,
                0xBFFFF,
                0xCFFFE,
                0xCFFFF,
                0xDFFFE,
                0xDFFFF,
                0xEFFFE,
                0xEFFFF,
                0xFFFFE,
                0xFFFFF,
                0x10FFFE,
                0x10FFFF,
            ]
        )
    )
    return set(control_chars + special_chars + non_chars)


INVALID_ATTRIBUTE_NAME_CHARS = make_invalid_attr_name_chars()
