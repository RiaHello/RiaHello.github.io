#!/usr/bin/env bash
set -euo pipefail

# Rebuild the monotonic, independently seekable portrait clip from the retained
# original optimized video. Requires ffmpeg with minterpolate and libx264.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

# Original 24 fps poses: reverse the continuous left turn 8..30, then 65..78.
# Keep the natural left-to-front motion (including its blink): skipping those
# poses caused double facial features in optical-flow interpolation near center.
# OBMC fills smaller pose gaps at 60 fps. Padded anchors: 10, 120, 190.
ffmpeg -hide_banner -loglevel error -y \
  -i src/assets/contact-portrait.mp4 \
  -filter_complex '[0:v]split=2[l][r];[l]trim=start_frame=8:end_frame=31,reverse,setpts=N/(12*TB)[left];[r]trim=start_frame=65:end_frame=79,setpts=N/(12*TB)[right];[left][right]concat=n=2:v=1:a=0,setpts=N/(12*TB),fps=12,tpad=start_duration=0.166667:stop_duration=0.166667:start_mode=clone:stop_mode=clone,minterpolate=fps=60:mi_mode=mci:mc_mode=obmc:me_mode=bidir:me=umh:mb_size=16:search_param=64:vsbmc=0:scd=none,format=yuv420p[v]' \
  -map '[v]' -an -c:v libx264 -preset fast -crf 24 \
  -g 1 -keyint_min 1 -bf 0 -movflags +faststart src/assets/contact-gaze.mp4

ffmpeg -hide_banner -loglevel error -y -ss 2.0 \
  -i src/assets/contact-gaze.mp4 -frames:v 1 -q:v 2 src/assets/contact-portrait-poster.jpg
