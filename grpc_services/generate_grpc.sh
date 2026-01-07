#!/bin/bash

# Generate Python gRPC code from proto files

PROTO_DIR="./grpc_services/protos"
OUT_DIR="./grpc_services/generated"

mkdir -p $OUT_DIR

python -m grpc_tools.protoc \
    -I$PROTO_DIR \
    --python_out=$OUT_DIR \
    --grpc_python_out=$OUT_DIR \
    $PROTO_DIR/orchestrator.proto

# Fix imports in generated files
sed -i '' 's/^import orchestrator_pb2/from . import orchestrator_pb2/' $OUT_DIR/orchestrator_pb2_grpc.py 2>/dev/null || \
sed -i 's/^import orchestrator_pb2/from . import orchestrator_pb2/' $OUT_DIR/orchestrator_pb2_grpc.py 2>/dev/null

echo "gRPC code generation complete!"
