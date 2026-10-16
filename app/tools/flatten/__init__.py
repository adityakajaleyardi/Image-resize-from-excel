"""The bulk PDF flattening tool.

The flattening itself belongs to the separate `flatten-pdf` distribution, which
is installed as an ordinary dependency. Nothing here reimplements it; this
package only moves bytes between the browser and `flatten_bytes`.
"""

TOOL_ID = "flatten"
