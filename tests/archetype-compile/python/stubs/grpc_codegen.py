"""harness-only: generate Python code from grpc-pattern.md's .proto blocks the way
grpc-pattern-python.md's "Code Generation" block does (grpc_tools.protoc, -I proto/, --python_out,
--grpc_python_out and --pyi_out into gen/). All three .proto files are generated, as `buf generate`
would; protoc only emits code for the files it is given, and widget_service.proto imports the others."""
import pathlib
import sys

import grpc_tools
from grpc_tools import protoc

root = pathlib.Path(__file__).resolve().parent
files = ["yourapp/v1/widget_service.proto", "yourapp/v1/widget.proto", "yourapp/v1/common.proto"]

common = root / "proto" / "yourapp" / "v1" / "common.proto"
text = common.read_text(encoding="utf-8")
needed = ['import "yourapp/v1/widget.proto";', 'import "google/protobuf/timestamp.proto";']
missing = [imp for imp in needed if imp not in text]
if missing:
    # grpc-pattern.md (not a Python block) uses Widget, WidgetStatus and Timestamp in common.proto
    # without importing them; protoc rejects that. Reported, and patched here so the Python can be checked.
    print("NOTE grpc-pattern.md common.proto lacks: " + " ".join(missing), file=sys.stderr)
    common.write_text(text.rstrip() + "\n\n" + "\n".join(missing) + "\n", encoding="utf-8")

(root / "gen").mkdir(exist_ok=True)
well_known = str(pathlib.Path(grpc_tools.__file__).parent / "_proto")
rc = protoc.main(["protoc", "-Iproto", f"-I{well_known}", "--python_out=gen", "--grpc_python_out=gen",
                  "--pyi_out=gen", *(f"proto/{f}" for f in files)])
sys.exit(rc)
