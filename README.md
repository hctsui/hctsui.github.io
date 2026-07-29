# Hung-Chun Tsui — GitHub Pages website

This folder is ready to publish at:

**https://hctsui.github.io**

## Fastest upload method (no command line)

1. Open your `hctsui.github.io` repository on GitHub.
2. Click **Add file → Upload files**.
3. Open this folder and drag **all files and the `assets` folder** into the upload area.
   - Upload the contents of this folder, not the outer folder itself.
4. At the bottom, enter a message such as `Add personal website`.
5. Click **Commit changes**.
6. Open **Settings → Pages**.
7. Under **Build and deployment**, choose:
   - Source: **Deploy from a branch**
   - Branch: **main**
   - Folder: **/(root)**
8. Save, then visit `https://hctsui.github.io`.

## Replace the profile image

1. Put your photo in `assets/`, for example:
   `assets/profile.jpg`
2. In `index.html`, find:

```html
<img src="assets/profile-placeholder.svg" alt="HC monogram placeholder">
```

3. Replace it with:

```html
<img src="assets/profile.jpg" alt="Portrait of Hung-Chun Tsui">
```

4. You may also remove the line:
   `Replace this image with your portrait later.`

## Edit content later

Most content is directly inside `index.html`.

Useful search terms:
- `About me`
- `Research interests`
- `Preprints`
- `Upcoming`
- `Education`
- `Get in touch`

After editing a file on GitHub, click **Commit changes**. GitHub Pages will republish automatically.

## Included files

- `index.html` — all website content
- `assets/style.css` — layout and visual design
- `assets/script.js` — mobile navigation and current year
- `assets/profile-placeholder.svg` — temporary profile image
- `assets/favicon.svg` — browser-tab icon
- `.nojekyll` — serves the files directly without Jekyll processing
