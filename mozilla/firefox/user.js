// Portable Firefox preferences for this dotfiles repo.
// Copy or symlink this file into the active Firefox profile directory.

// Enable chrome/userChrome.css and chrome/userContent.css.
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);

// Keep Firefox aligned with the desktop theme.
user_pref("browser.theme.content-theme", 0);
user_pref("browser.theme.toolbar-theme", 0);
user_pref("layout.css.prefers-color-scheme.content-override", 0);

// Quiet first-run and promotional surfaces.
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.addons", false);
user_pref("browser.newtabpage.activity-stream.asrouter.userprefs.cfr.features", false);
user_pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);
user_pref("browser.newtabpage.activity-stream.showSponsored", false);
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false);

// Reduce telemetry and studies.
user_pref("app.shield.optoutstudies.enabled", false);
user_pref("browser.discovery.enabled", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.archive.enabled", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("toolkit.telemetry.unified", false);

// Privacy defaults that preserve normal browsing behavior.
user_pref("browser.search.suggest.enabled", false);
user_pref("browser.urlbar.suggest.quicksuggest.nonsponsored", false);
user_pref("browser.urlbar.suggest.quicksuggest.sponsored", false);
user_pref("dom.security.https_only_mode", true);
user_pref("privacy.donottrackheader.enabled", true);
user_pref("privacy.globalprivacycontrol.enabled", true);
user_pref("privacy.trackingprotection.enabled", true);
user_pref("privacy.trackingprotection.socialtracking.enabled", true);

// Explicit resets — these were set previously and linger in prefs.js unless overridden here.
user_pref("gfx.webrender.all", false);
user_pref("gfx.webrender.compositor.force-enabled", false);
user_pref("gfx.canvas.accelerated", false);
user_pref("media.ffmpeg.vaapi.enabled", false);
user_pref("media.hardware-video-decoding.force-enabled", false);

// UI and scrolling feel.
user_pref("browser.compactmode.show", true);
user_pref("browser.tabs.inTitlebar", 1);
user_pref("general.autoScroll", true);
user_pref("mousewheel.default.delta_multiplier_y", 80);
user_pref("widget.gtk.overlay-scrollbars.enabled", true);
