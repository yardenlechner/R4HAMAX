# IBM references

Mapping reviewed on 2026-09-09. Confirm against the z/OS/RMF release
installed at your site. This repository contains original code and
explanations, not a copy of the IBM manuals.

| Reference | Used for |
|---|---|
| [SMF 70 header and self-defining section](https://www.ibm.com/docs/en/zos/3.2.0?topic=mapping-headerself-defining-section) | Header offsets, RDW origin, triplets |
| [RMF product section](https://www.ibm.com/docs/en/zos/3.2.0?topic=mapping-rmf-product-section) | Packed date/time/duration, FLA offset and flags |
| [CPU control section](https://www.ibm.com/docs/en/zos/3.2.0?topic=s1cpia-cpu-control-section) | LAC offset 36, STF bit 3, singleton section |
| [EXECIO](https://www.ibm.com/docs/en/zos/3.2.0?topic=commands-execio) | VBS logical-record I/O, counts, EOF, FINIS |
| [z/OS introduction and release guide](https://publibz.boulder.ibm.com/epubs/pdf/e0z3a116.pdf) | EXECIO spanned-record support introduced in V2R1 |
| [SMF dump generation](https://www.ibm.com/docs/en/abo/2.2.0?topic=assistant-smf-dump-generation) | IFASMFDP/IFASMFDL JCL and subtype selection pattern |
| [IFASMFDL parameters](https://www.ibm.com/docs/SSLTBW_3.2.0/com.ibm.zos.v3r2.ieag200/dumplopt.htm) | DUMP versus ARCHIVE/DELETE, filters |
| [IBM sub-capacity explanation](https://www.ibm.com/about/software-licensing/assets/zsw_licensing/IBM-Z-Software-Webpages.pdf) | LAC at interval end, hourly means, simultaneous peaks |
| [Are You Using the Right 4-Hour Rolling Average?](https://www.ibm.com/support/pages/system/files/inline-files/Are_You_Using_the_Right_4-Hour_Rolling_Average%3F.pdf) | Recorded interval values versus hourly reporting |
| [TSO/E VERIFY](https://www.ibm.com/docs/en/zos/3.2.0?topic=functions-verify) | Parameter validation |

The hourly mode in R4HAMAX deliberately defines a sample-hour arithmetic
mean. It does not claim to reproduce all SCRT rules or hour attribution.

## Additional references from the code review

| Reference | Used for |
|---|---|
| [SMFPRMxx statements and parameters](https://www.ibm.com/docs/en/zos/3.1.0?topic=ssmfsp-statements-parameters-smfprmxx) | SID national characters and period |
| [GRBSMFR retrieval service](https://www.ibm.com/docs/en/zos/3.1.0?topic=sr-obtaining-smf-record-data-from-data-set-log-stream-grbsmfr) | RMF reassembly is distinct from VBS record assembly |
| [RMF Data Gatherer Programmer's Guide](https://www.ibm.com/docs/SSLTBW_3.2.0/pdf/grbdp00_v3r2.pdf) | Independent example section placement and triplet layout |
| [CP CPU LPAR table](https://www.ibm.com/docs/en/zp-and-ca/3.1.0?topic=tables-cp-cpu-lpar-h) | MSU_4HRA is available for the writing partition |
| [WLM license charges](https://www.ibm.com/docs/SSLTBW_3.2.0/com.ibm.zos.v3r2.ieaw100/lcharg.htm) | Zero-initialized rolling-average history at IPL |
| [WLM changes for Boost](https://www.ibm.com/docs/en/zos/3.1.0?topic=considerations-wlm-changes) | Long-term MSU accounting during Boost |
| [TSO/E Customization](https://www.ibm.com/docs/en/SSLTBW_3.1.0/pdf/ikjc200_v3r1.pdf) | IKJEFT1B handling of REXX return codes |
| [Log stream dump parameters](https://www.ibm.com/docs/en/zos/3.2.0?topic=program-specifying-parameters-smf-log-stream-dump) | Buffered records and SMARTENDPOINT considerations |

These references do not replace validation against the installed RMF mapping,
site collection settings and real records. See [REVIEW.md](REVIEW.md).
