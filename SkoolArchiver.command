#!/bin/bash
# Wrapper cu → Skool Downloader
cd "$(dirname "$0")" || exit 1
exec bash "./SkoolDownloader.command"
