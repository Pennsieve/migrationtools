#!/bin/bash

# Ensure an input argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <S3 subpath>"
    exit 1
fi

# Input arg
S3_SUBPATH="$1"

# Extract the last directory name from the input path
LAST_DIR=$(basename "$S3_SUBPATH")

# Build the full S3 source path
S3_SOURCE="s3://org-ieeg-data/$S3_SUBPATH"

# Build the local destination path
LOCAL_DEST="~/data/$LAST_DIR"

# Run the AWS S3 copy command
echo "Running: aws s3 cp \"$S3_SOURCE\" \"$LOCAL_DEST\" --recursive"
aws s3 cp "$S3_SOURCE" "$LOCAL_DEST" --recursive
