"""CSS generated from the current scale, background and animation settings."""

from __future__ import annotations

from pathlib import Path

BACKGROUNDS = {
    "aurora": ("Aurora",
               "radial-gradient(circle at 15% 10%, alpha(#5b3cc4, 0.55), transparent 55%),"
               "radial-gradient(circle at 90% 85%, alpha(#0f8fb3, 0.45), transparent 50%),"
               "linear-gradient(160deg, #0d0f1c, #111527 60%, #0a0c16)"),
    "midnight": ("Midnight", "linear-gradient(180deg, #0b1a33, #050a14)"),
    "ember": ("Ember",
              "radial-gradient(circle at 80% 0%, alpha(#c2410c, 0.5), transparent 60%),"
              "linear-gradient(180deg, #1a0f0c, #0c0807)"),
    "forest": ("Forest",
               "radial-gradient(circle at 10% 90%, alpha(#15803d, 0.45), transparent 55%),"
               "linear-gradient(180deg, #0b1510, #060a08)"),
    "black": ("Pure black", "none"),
    "wallpaper": ("GNOME wallpaper", None),
}


def gnome_wallpaper() -> Path | None:
    """Return the current GNOME (dark) wallpaper file, if it is a readable image."""
    try:
        from gi.repository import Gio
        source = Gio.SettingsSchemaSource.get_default()
        if source is None or source.lookup("org.gnome.desktop.background", True) is None:
            return None
        settings = Gio.Settings.new("org.gnome.desktop.background")
        for key in ("picture-uri-dark", "picture-uri"):
            uri = settings.get_string(key)
            if uri:
                path = Path(Gio.File.new_for_uri(uri).get_path() or "")
                if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    return path
    except Exception:
        return None
    return None


def build_css(scale: float, background: str, animations: bool) -> str:
    def px(v: float) -> str:
        return f"{max(1, round(v * scale))}px"

    bg = BACKGROUNDS.get(background, BACKGROUNDS["aurora"])[1]
    if background == "wallpaper":
        wp = gnome_wallpaper()
        if wp:
            uri = wp.as_uri().replace('"', "%22")
            bg = (f'linear-gradient(alpha(black, 0.55), alpha(black, 0.75)), url("{uri}")')
        else:
            bg = BACKGROUNDS["aurora"][1]
    t = "transition: all 180ms cubic-bezier(0.2, 0.8, 0.2, 1);" if animations else "transition: none;"

    return f"""
window.living-room {{ background-color: #07080f; color: #f2f4ff; }}
.lr-background {{ background-color: #07080f; background-image: {bg};
    background-size: cover; background-position: center; }}
.lr-header {{ padding: {px(36)} {px(64)} {px(8)} {px(64)}; }}
.lr-title {{ font-size: {px(30)}; font-weight: 800; letter-spacing: {px(6)}; }}
.lr-clock {{ font-size: {px(40)}; font-weight: 700; }}
.lr-date {{ font-size: {px(18)}; color: alpha(#f2f4ff, 0.7); }}
.lr-content {{ padding: {px(8)} {px(64)} {px(32)} {px(64)}; }}
.lr-section {{ font-size: {px(20)}; font-weight: 800; letter-spacing: {px(3)};
    color: alpha(#f2f4ff, 0.65); margin-top: {px(24)}; margin-bottom: {px(12)}; }}
.lr-page-title {{ font-size: {px(40)}; font-weight: 800; }}
.lr-subtitle {{ font-size: {px(19)}; color: alpha(#f2f4ff, 0.7); }}
.lr-empty {{ font-size: {px(20)}; color: alpha(#f2f4ff, 0.6); padding: {px(24)}; }}

button.card {{ background: alpha(#ffffff, 0.06); border-radius: {px(22)};
    border: {px(3)} solid transparent; padding: {px(16)}; box-shadow: none; {t} }}
button.card.big {{ min-width: {px(260)}; min-height: {px(230)}; }}
button.card.small {{ min-width: {px(200)}; min-height: {px(170)}; }}
button.card:hover {{ background: alpha(#ffffff, 0.10); }}
button.card:focus, button.card:focus-visible {{ background: alpha(#ffffff, 0.16);
    border-color: #7aa2ff; box-shadow: 0 0 0 {px(4)} alpha(#7aa2ff, 0.35), 0 {px(16)} {px(40)} alpha(black, 0.5);
    transform: scale(1.06); outline: none; }}
button.card.missing {{ opacity: 0.45; }}
button.card.moving {{ border-color: #fbbf24; box-shadow: 0 0 0 {px(4)} alpha(#fbbf24, 0.4); }}
.card-name {{ font-size: {px(21)}; font-weight: 600; }}
button.card.small .card-name {{ font-size: {px(18)}; }}
button.card.add-card {{ background: transparent; border: {px(3)} dashed alpha(#ffffff, 0.25); }}
button.card.add-card:focus {{ border-style: solid; }}
.add-plus {{ font-size: {px(96)}; font-weight: 300; color: alpha(#f2f4ff, 0.8); }}
.card-star {{ color: #fbbf24; font-size: {px(22)}; }}

button.tile {{ background: alpha(#ffffff, 0.07); border-radius: {px(16)};
    border: {px(3)} solid transparent; padding: {px(14)} {px(24)}; min-height: {px(44)};
    font-size: {px(22)}; box-shadow: none; {t} }}
button.tile:focus, button.tile:focus-visible {{ background: alpha(#ffffff, 0.16);
    border-color: #7aa2ff; box-shadow: 0 0 0 {px(4)} alpha(#7aa2ff, 0.3); outline: none; }}
button.tile.destructive:focus {{ border-color: #f87171; }}
button.tile.moving {{ border-color: #fbbf24; }}
button.round {{ border-radius: 999px; min-width: {px(56)}; min-height: {px(56)}; padding: {px(8)}; }}
button.key {{ min-width: {px(64)}; min-height: {px(56)}; padding: {px(4)}; font-size: {px(24)}; font-weight: 700; }}
.tile-value {{ color: #9db8ff; font-weight: 700; }}
.tile-label {{ font-size: {px(22)}; }}
.tile-desc {{ font-size: {px(16)}; color: alpha(#f2f4ff, 0.6); }}

.lr-dialog {{ background: #151a2c; border-radius: {px(28)}; padding: {px(40)};
    border: 1px solid alpha(#ffffff, 0.08); box-shadow: 0 {px(30)} {px(80)} alpha(black, 0.6); }}
.lr-scrim {{ background: alpha(black, 0.6); }}

.lr-hints {{ background: alpha(black, 0.35); padding: {px(14)} {px(64)}; }}
.hint {{ font-size: {px(18)}; color: alpha(#f2f4ff, 0.85); margin-right: {px(28)}; }}
.hint-key {{ background: alpha(#ffffff, 0.15); border-radius: {px(8)}; padding: {px(2)} {px(10)};
    font-weight: 800; margin-right: {px(8)}; font-size: {px(18)}; }}
.lr-toast {{ background: #1f2640; border-radius: 999px; padding: {px(14)} {px(32)};
    font-size: {px(20)}; margin-bottom: {px(90)}; box-shadow: 0 {px(10)} {px(30)} alpha(black, 0.5); }}
.lr-toast.error {{ background: #5b1d1d; }}

entry.lr-search {{ font-size: {px(26)}; min-height: {px(60)}; border-radius: {px(16)};
    padding: 0 {px(20)}; background: alpha(#ffffff, 0.08); }}
.diag-btn {{ background: alpha(#ffffff, 0.08); border-radius: {px(10)}; padding: {px(8)} {px(14)};
    font-size: {px(18)}; min-width: {px(80)}; }}
.diag-btn.on {{ background: #4f7cff; color: white; }}
.diag-log {{ font-family: monospace; font-size: {px(16)}; color: alpha(#f2f4ff, 0.8); }}
levelbar block.filled {{ background: #7aa2ff; }}
"""
