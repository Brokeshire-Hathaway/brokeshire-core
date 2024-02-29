#!/bin/sh

set -e  # Exit immediately if a command exits with a non-zero status.

pdm sync
pdm start
