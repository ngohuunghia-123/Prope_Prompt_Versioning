"""Package the bundled local extension using stdlib ZIP/OPC, without publisher login.

Manifest layout follows the output of Microsoft's vsce 4.1.0 and the VSIX schema:
https://learn.microsoft.com/visualstudio/extensibility/vsix-extension-schema-2-0-reference
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
NAMESPACE = "http://schemas.microsoft.com/developer/vsx-schema/2011"
ET.register_namespace("", NAMESPACE)


def element(parent: ET.Element, name: str, text: str | None = None, **attributes: str):
    child = ET.SubElement(parent, f"{{{NAMESPACE}}}{name}", attributes)
    child.text = text
    return child


manifest = ET.Element(f"{{{NAMESPACE}}}PackageManifest", {"Version": "2.0.0"})
metadata = element(manifest, "Metadata")
element(
    metadata,
    "Identity",
    Language="en-US",
    Id=PACKAGE["name"],
    Version=PACKAGE["version"],
    Publisher=PACKAGE["publisher"],
)
element(metadata, "DisplayName", PACKAGE["displayName"])
element(metadata, "Description", PACKAGE["description"])
element(metadata, "Categories", ",".join(PACKAGE["categories"]))
properties = element(metadata, "Properties")
for key, value in {
    "Engine": PACKAGE["engines"]["vscode"],
    "ExtensionKind": ",".join(PACKAGE["extensionKind"]),
    "ExecutesCode": "true",
}.items():
    element(properties, "Property", Id=f"Microsoft.VisualStudio.Code.{key}", Value=value)
element(metadata, "License", "extension/LICENSE.txt")
element(element(manifest, "Installation"), "InstallationTarget", Id="Microsoft.VisualStudio.Code")
element(manifest, "Dependencies")
assets = element(manifest, "Assets")
for kind, path in {
    "Microsoft.VisualStudio.Code.Manifest": "package.json",
    "Microsoft.VisualStudio.Services.Content.Details": "README.md",
    "Microsoft.VisualStudio.Services.Content.License": "LICENSE.txt",
}.items():
    element(assets, "Asset", Type=kind, Path=f"extension/{path}", Addressable="true")
content_types = ET.Element("Types", {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"})
for extension, mime in {
    ".cjs": "application/javascript",
    ".mjs": "application/javascript",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".vsixmanifest": "text/xml",
}.items():
    ET.SubElement(content_types, "Default", {"Extension": extension, "ContentType": mime})
files = [
    "package.json",
    "package.nls.json",
    "package.nls.vi.json",
    "README.md",
    "LICENSE.txt",
    "dist/extension.cjs",
    "dist/mcp-stdio.mjs",
    "dist/media/connector.js",
    "dist/media/connector.css",
    "dist/media/.vite/manifest.json",
    "dist/media/assets/mascot/avatar.webp",
    "dist/media/assets/mascot/empty-state.webp",
    "dist/media/assets/mascot/idle.webp",
    "dist/media/assets/mascot/mascot-animate.gif",
    "l10n/bundle.l10n.json",
    "l10n/bundle.l10n.vi.json",
]
target = ROOT / "dist/prope-connector.vsix"
for name in files:
    if not (ROOT / name).is_file():
        raise FileNotFoundError(name)
with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
    archive.writestr("extension.vsixmanifest", ET.tostring(manifest, encoding="utf-8", xml_declaration=True))
    archive.writestr("[Content_Types].xml", ET.tostring(content_types, encoding="utf-8", xml_declaration=True))
    for name in files:
        archive.write(ROOT / name, f"extension/{name}")
print(f"VSIX: {target.name} ({target.stat().st_size:,} bytes, {len(files) + 2} files)")
