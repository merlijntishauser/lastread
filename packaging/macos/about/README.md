# The About picture

`About-light.png` and `About-dark.png` (beside the app's other pictures, in
`packaging/macos`) show Lastread as a tabletop proof press. The Kobo is
locked on the bed as the forme. The carriage and its cylinder are the
sync, the one lit part, running on bearers exactly type-high. The proof
of your Hardcover shelf lies on the feed board, with red carets where the
sync changes something. A cable runs from the Kobo to the trip box:
plugging in starts the run. The galley holds books waiting to go on the
Kobo, and the ink disc with its brayer sits on the front ledge.

`build.mjs` draws it with the anatomy kit (`kit/`, MIT, see
`kit/LICENSE`), on the app's own paper and red, so the picture sits on
the About window without an edge. The kit is only used to make the
pictures; nothing of it goes into the app.

To draw them again, with Node and headless Chrome:

```
node packaging/macos/about/build.mjs --light --px 1440 --out about-light.html
node packaging/macos/about/build.mjs --px 1440 --out about-dark.html
```

Then take a picture of the `svg` in each page at 1x, 1452 x 812 with
the 6 px margin around it, and save them as `About-light.png` and
`About-dark.png`. `--px 1440` makes the lines as thick as the window
shows them at 2x. Before saving, check that the corners are the app's
sheet colour (`#fbfbf8` and `#171a1e`), and that no line ends in mid-air.
