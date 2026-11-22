The fonts in this folder are not part of lastread's own code and
are not under its MIT licence. Each is under the SIL Open Font License 1.1;
the full text, with the copyright notice, is next to it.

Atkinson Hyperlegible Next
                   AtkinsonHyperlegibleNext-latin.woff2, AtkinsonHyperlegibleNext-latin-ext.woff2,
                   AtkinsonHyperlegibleNext-italic-latin.woff2, AtkinsonHyperlegibleNext-italic-latin-ext.woff2
                   AtkinsonHyperlegibleNext-LICENSE.txt
                   by the Braille Institute of America, Applied Design Works
                   https://github.com/googlefonts/atkinson-hyperlegible-next
Literata           Literata-latin.woff2, Literata-latin-ext.woff2
                   Literata-LICENSE.txt
                   by TypeTogether
                   https://github.com/googlefonts/literata
Schibsted Grotesk  SchibstedGrotesk-latin.woff2, SchibstedGrotesk-latin-ext.woff2,
                   SchibstedGrotesk-italic-latin.woff2, SchibstedGrotesk-italic-latin-ext.woff2
                   SchibstedGrotesk-LICENSE.txt
                   by Bakken & Bæck, Henrik Kongsvoll
                   https://github.com/schibsted/schibsted-grotesk
Source Serif 4     SourceSerif4-latin.woff2, SourceSerif4-latin-ext.woff2
                   SourceSerif4-LICENSE.txt
                   by Frank Grießhammer
                   https://github.com/adobe-fonts/source-serif

The page is set in Atkinson Hyperlegible Next (everything but book titles)
and Literata (book titles, page heads, how far a book is read). Schibsted
Grotesk and Source Serif 4 are no longer used by the page; they stay because
the Mac app's packaging draws its disk image art and its widget with them
(packaging/macos/art.py, build.sh).

The files are the variable woff2 subsets (latin and latin-ext) as served by
Google Fonts, unchanged: Atkinson Hyperlegible Next v7, roman and italic,
weights 400 to 800; Literata v40, roman, weights 400 to 800; Schibsted
Grotesk v7, roman and italic, weights 400 to 800; Source Serif 4 v15, roman,
weights 400 to 700, optical size 8 to 60. They are served by the tool itself
so that the page loads nothing from elsewhere. None of the four declares a
Reserved Font Name in these copies.
