# Run with repodock (browser extension)

Adds two things to GitHub, in Chrome, Edge and Firefox:

- A **Run with repodock** button at the top of every project page. It opens the
  project in [repodock](https://github.com/UmutAlisoglu/repodock), which asks
  whether to download it. Nothing runs until you press Run there and confirm.
- A **Download for Windows** (or macOS, or Linux) button on release pages,
  pointing at the file that suits your computer, with that file marked in the list.

It needs no permissions and sends nothing anywhere: it only reads the GitHub page
you're looking at. The Run button needs repodock 0.3 or newer, installed with the
Windows installer or with "Open Run with repodock links" turned on in its Settings.

## Install

Until it's in the browser stores, load it from this folder:

- **Chrome or Edge:** download this repository (Code > Download ZIP) and unzip it.
  Open `chrome://extensions` (or `edge://extensions`), turn on **Developer mode**,
  click **Load unpacked** and pick the `extension` folder.
- **Firefox:** open `about:debugging#/runtime/this-firefox`, click **Load Temporary
  Add-on** and pick `extension/manifest.json`. Firefox removes it again when it
  restarts, until it's on addons.mozilla.org.

## Development

`node extension/test.js` checks which release file gets picked for each system.
`fit.js` follows the same rules as repodock's own `asset_fit` in `github.py`.
