# Extraction problems (from Step 2 report)

**Problems, most damaging first:**
1. **References and appendices get the wrong section.** None of the bookmark lists includes "References", and Attention's appendix isn't in its list either. Everything after the conclusion is labelled `Conclusion` until the next bookmark:
   - Attention: pages 10–15, including all references and the attention-visualisation appendix
   - Moshi: references on pages 42–52
   - Dynamic Chunking: references on pages 25–30

   This would produce false "Conclusion" citations, and the reference lists are full of keyword matches.
2. **Superscripts and subscripts are flattened, which changes numbers.** In Attention's Table 2, `1.0 · 10^20` FLOPs comes out as `1.0 · 1020`, and `d_k` comes out as `dk`. Footnote markers stick to words (`Alexa1`, `4To illustrate`). A model reading these blocks could quote a wrong number with a correct citation.
3. **Tables lose their structure.** Rows are flattened into lists of values, and the header row merges into the first data row (`EN-DE\nEN-FR\nEN-DE\nEN-FR\nByteNet [18]\n23.75…`). Empty cells disappear, so it becomes unclear which column a value belongs to. There are 4, 19 and 8 tables respectively.
4. **Equations break apart.** Attention's Eq. 1 is split over three blocks (`softmax(QKT`, `√dk`, `)V (1)`). Moshi's big curly braces come out as private-use characters (``). Dynamic Chunking uses mathematical italic Unicode (`𝐿`, `𝑁0`), which won't match a plain `L` or `N0` in a keyword search.
5. **Text inside figures becomes noise.** Attention's visualisation pages produce one word per block (`<pad>` ×20, `Law` ×8). Moshi's charts produce axis ticks (`1.0`, `1.5`…). Dynamic Chunking page 39 has rotated text one character per line, plus hex byte labels. This accounts for most of the tiny blocks.
6. **Repeated headers and page numbers.** Moshi's running title appears in 67 blocks. Standalone page-number blocks are common in all three papers (118 in Moshi alone).
7. **Floating tables and figures get the section where they physically sit.** Attention's Table 2 (a Results table) is labelled `Regularization`, because it floats to the top of page 8, above the Results heading.
8. **The same title appears in different places.** Moshi has two "Architecture" and two "Audio Tokenization" headings. Dynamic Chunking's "Dynamic Chunking" is both §2.2 and a related-work subsection. `section_path` tells them apart, but `section` alone doesn't. The bookmarks also don't include section numbers, though the heading blocks do (`3.2.1\nScaled Dot-Product Attention`).
9. **Words split at line breaks:** 11, 173 and 38 hyphenated breaks (e.g. `multi-\nplicative`).
10. **Two-column mixing is not a problem.** All three papers are single-column. My check flagged Moshi pages 34 and 59, but those are side-by-side charts, not text columns.
