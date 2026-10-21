# HEVC WPP sample with zeroed entry_point_offset values

Reproduction material for an Icaros Shell Extensions report: HEVC streams that use WPP
(`entropy_coding_sync_enabled_flag = 1`) but carry `entry_point_offset_minus1[i] = 0` for every
substream decode correctly on sequential decoders and break on decoders that start the wavefront
rows from the signalled entry points.

| File | Entry points | `ffmpeg` default | `ffmpeg -thread_type slice` |
| --- | --- | --- | --- |
| `wpp_ok.mp4` | correct (sum of offsets = slice size) | OK | OK |
| `wpp_zero_ep.mp4` | all zero | OK, pixel-identical to `wpp_ok.mp4` | `cu_qp_delta ... outside the valid range`, `CABAC_MAX_BIN` |

The two files contain byte-identical slice data; only the `entry_point_offset_minus1` fields of the
slice headers differ (16 fields per slice, 48 slices).

How the sample was made:

```
ffmpeg -f lavfi -i "testsrc2=size=1920x1080:rate=24,format=yuv420p10le" -t 2 \
  -c:v libx265 -preset medium -crf 18 -x265-params "wpp=1:bframes=0:keyint=12:min-keyint=12" \
  -tag:v hvc1 wpp_ok.mp4
ffmpeg -i wpp_ok.mp4 -c:v copy -bsf:v hevc_mp4toannexb -f hevc wpp_ok.h265
ffmpeg -loglevel trace -i wpp_ok.h265 -c:v copy -bsf:v trace_headers -f null - 2>&1 \
  | grep -E "^\[trace_headers" | sed -E 's/^\[trace_headers @ [0-9a-f]+\] +//' > wpp_ok.trace.txt
python zero_entry_points.py wpp_ok.h265 wpp_ok.trace.txt wpp_zero_ep.h265
ffmpeg -r 24 -i wpp_zero_ep.h265 -c:v copy -tag:v hvc1 wpp_zero_ep.mp4
```

`zero_entry_points.py` zeroes the `entry_point_offset_minus1` bits in the RBSP of every VCL NAL
(positions taken from the `trace_headers` output) and re-inserts emulation-prevention bytes.

`wpp_ok_shell.png` and `wpp_zero_ep_shell.png` are the thumbnails the Windows shell returned for the
two files with Icaros 3.3.6 registered for `.mp4` (`IShellItemImageFactory::GetImage`,
`SIIGBF_THUMBNAILONLY`, 256 px).

The synthetic content is `testsrc2`; no copyrighted material is included.
