/* web-themes - erzeugt von `python -m web_themes build`, nicht von Hand aendern */
(function (global) {
  "use strict";
  // Name -> dunkel, fuer data-bs-theme
  var DARK = {"ascot": true, "beastie": true, "bebox": true, "bluesy": true, "boing": true, "brick": false, "brotkasten": true, "bunty": true, "christophorus": true, "classic-navy": true, "classic-terminal": true, "clipper": false, "commandr": true, "corleone": true, "crimson": true, "cupertino": false, "fifty-eight": true, "flughund": true, "geeko": true, "gemstone": false, "golden-brown": true, "goldfinder": true, "goldrunner": true, "hercules": true, "hulkula": true, "joker": true, "lenseflare": true, "luna": true, "marley": true, "metropolis": true, "miami": true, "minty": true, "motif": true, "next": true, "plan9": false, "platoon": true, "racing": true, "razzy": true, "spiderized": true, "synthwave": true, "warp": true};
  var SELECTABLE = [{"name": "ascot", "title": "Ascot"}, {"name": "beastie", "title": "Beastie"}, {"name": "bebox", "title": "BeBox"}, {"name": "bluesy", "title": "Bluesy"}, {"name": "brick", "title": "Brick"}, {"name": "bunty", "title": "Bunty"}, {"name": "christophorus", "title": "Christophorus"}, {"name": "classic-navy", "title": "Classic Navy"}, {"name": "classic-terminal", "title": "Classic Terminal"}, {"name": "clipper", "title": "Clipper"}, {"name": "corleone", "title": "Corleone"}, {"name": "crimson", "title": "Crimson"}, {"name": "cupertino", "title": "Cupertino"}, {"name": "fifty-eight", "title": "Fifty-Eight"}, {"name": "flughund", "title": "Flughund"}, {"name": "gemstone", "title": "Gemstone"}, {"name": "golden-brown", "title": "Golden Brown"}, {"name": "goldfinder", "title": "Goldfinder"}, {"name": "goldrunner", "title": "Goldrunner"}, {"name": "hercules", "title": "Hercules"}, {"name": "joker", "title": "Joker"}, {"name": "lenseflare", "title": "Lenseflare"}, {"name": "marley", "title": "Marley"}, {"name": "metropolis", "title": "Metropolis"}, {"name": "miami", "title": "Miami"}, {"name": "minty", "title": "Minty"}, {"name": "motif", "title": "Motif"}, {"name": "next", "title": "Next"}, {"name": "platoon", "title": "Platoon"}, {"name": "racing", "title": "Racing"}, {"name": "razzy", "title": "Razzy"}, {"name": "spiderized", "title": "Spiderized"}];

  function apply(name, element) {
    var el = element || document.documentElement;
    if (!Object.prototype.hasOwnProperty.call(DARK, name)) {
      throw new Error("web-themes: unbekanntes Theme " + name);
    }
    el.setAttribute("data-web-theme", name);
    el.setAttribute("data-bs-theme", DARK[name] ? "dark" : "light");
    return name;
  }

  global.WebThemes = { apply: apply, dark: DARK, selectable: SELECTABLE };
})(window);
