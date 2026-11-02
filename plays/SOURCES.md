# Sources for the plays

All eight files were downloaded on 2026-11-01 from the same public Google Cloud Storage bucket
that the original lab reads (`gs://dataflow-samples/shakespeare/`), over HTTPS. The file sizes match
the bucket's own object listing. `tragedies/kinglear.txt` is byte-identical to `../data/kinglear.txt`.
The folders are a grouping chosen for this lab: four tragedies and four comedies.

| File | Bytes | SHA-256 |
|---|---|---|
| `comedies/asyoulikeit.txt` | 125179 | `eaa3526fe53859f34ecdf255712f9ecf0b2c903451d4755b2edaa2e2599cb0fc` |
| `comedies/midsummersnightsdream.txt` | 96508 | `684b22072f158a7965e942d7e9b633bf7c6c65b14a7b519631bbf2f826349370` |
| `comedies/muchadoaboutnothing.txt` | 123413 | `fad832e284ccabb6fcb5dc3dd34d2636a07358d6474f10eed8e9ed98050208ee` |
| `comedies/twelfthnight.txt` | 116759 | `68a44a35e82462d4f0217d2a40db874a431d666626691a806b63339118831039` |
| `tragedies/hamlet.txt` | 182567 | `1846810b98f3dce4174a488cd19f3e7ceabff2a4b00487089fbcb2891003d847` |
| `tragedies/kinglear.txt` | 157283 | `674a2725884307c96398440497c889ad8cecccedf5689df85e6b0faabe4e0fe8` |
| `tragedies/macbeth.txt` | 105404 | `339afa674ac54e5038bd610056e87b0ba70f6543b2fbcfea421bfd0fbbc21e7f` |
| `tragedies/othello.txt` | 156449 | `e1590d00e121e53587157fa952e0da4070b76721599ebcedce3bb698228adbab` |

To fetch one again:

```bash
curl -O https://storage.googleapis.com/dataflow-samples/shakespeare/hamlet.txt
```
