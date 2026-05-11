from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Player SVGs — forward-leaning trader, dark navy suit, white shirt, red tie
# ---------------------------------------------------------------------------

_PLAYER_CONFIDENT = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160" width="120" height="160">
  <!-- Head -->
  <ellipse cx="60" cy="30" rx="22" ry="24" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="3"/>
  <!-- Hair -->
  <ellipse cx="60" cy="12" rx="22" ry="10" fill="#2C1810" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Eyes -->
  <ellipse cx="52" cy="28" rx="3" ry="3.5" fill="#1A1A2E"/>
  <ellipse cx="68" cy="28" rx="3" ry="3.5" fill="#1A1A2E"/>
  <ellipse cx="53" cy="27" rx="1" ry="1.2" fill="white"/>
  <ellipse cx="69" cy="27" rx="1" ry="1.2" fill="white"/>
  <!-- Determined mouth -->
  <path d="M52 40 Q60 44 68 40" fill="none" stroke="#1A1A2E" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Neck -->
  <rect x="54" y="52" width="12" height="10" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Body / suit jacket -->
  <path d="M25 70 Q30 58 54 62 L60 90 L66 62 Q90 58 95 70 L100 130 L20 130 Z" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="2"/>
  <!-- White shirt -->
  <path d="M54 62 L58 90 L62 90 L66 62 L60 68 Z" fill="white" stroke="#CCCCCC" stroke-width="1"/>
  <!-- Red tie -->
  <path d="M58 64 L56 82 L60 88 L64 82 L62 64 Z" fill="#C0392B" stroke="#922B21" stroke-width="1.5"/>
  <!-- Left arm — slightly raised -->
  <path d="M25 70 L8 85 L12 95 L30 80" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="3" stroke-linejoin="round"/>
  <!-- Left hand -->
  <ellipse cx="10" cy="90" rx="7" ry="6" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Right arm — slightly raised -->
  <path d="M95 70 L112 85 L108 95 L90 80" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="3" stroke-linejoin="round"/>
  <!-- Right hand -->
  <ellipse cx="110" cy="90" rx="7" ry="6" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Legs -->
  <rect x="35" y="128" width="20" height="28" rx="4" fill="#1A1A2E" stroke="#111" stroke-width="2"/>
  <rect x="65" y="128" width="20" height="28" rx="4" fill="#1A1A2E" stroke="#111" stroke-width="2"/>
  <!-- Shoes -->
  <ellipse cx="45" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
  <ellipse cx="75" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
</svg>"""

_PLAYER_DEFLATED = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160" width="120" height="160">
  <!-- Head — slightly drooped -->
  <ellipse cx="60" cy="35" rx="22" ry="24" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="3"/>
  <!-- Hair -->
  <ellipse cx="60" cy="17" rx="22" ry="10" fill="#2C1810" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Eyes — half-closed / downward -->
  <ellipse cx="52" cy="33" rx="3" ry="2.5" fill="#1A1A2E"/>
  <ellipse cx="68" cy="33" rx="3" ry="2.5" fill="#1A1A2E"/>
  <!-- Sad brow lines -->
  <path d="M49 28 Q52 30 55 28" fill="none" stroke="#1A1A2E" stroke-width="2" stroke-linecap="round"/>
  <path d="M65 28 Q68 30 71 28" fill="none" stroke="#1A1A2E" stroke-width="2" stroke-linecap="round"/>
  <!-- Downward mouth -->
  <path d="M52 45 Q60 42 68 45" fill="none" stroke="#1A1A2E" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Neck -->
  <rect x="54" y="57" width="12" height="8" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Body — slumped, shoulders pulled in -->
  <path d="M32 72 Q34 62 54 65 L60 92 L66 65 Q86 62 88 72 L92 130 L28 130 Z" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="2"/>
  <!-- White shirt -->
  <path d="M54 65 L58 92 L62 92 L66 65 L60 70 Z" fill="white" stroke="#CCCCCC" stroke-width="1"/>
  <!-- Red tie — slack, crooked -->
  <path d="M58 67 L57 85 L60 90 L63 85 L62 67 Z" fill="#C0392B" stroke="#922B21" stroke-width="1.5" transform="rotate(3,60,78)"/>
  <!-- Left arm — hanging down -->
  <path d="M32 72 L18 110 L26 112 L38 80" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="3" stroke-linejoin="round"/>
  <!-- Left hand -->
  <ellipse cx="22" cy="112" rx="7" ry="6" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Right arm — hanging down -->
  <path d="M88 72 L102 110 L94 112 L82 80" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="3" stroke-linejoin="round"/>
  <!-- Right hand -->
  <ellipse cx="98" cy="112" rx="7" ry="6" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Legs -->
  <rect x="35" y="128" width="20" height="28" rx="4" fill="#1A1A2E" stroke="#111" stroke-width="2"/>
  <rect x="65" y="128" width="20" height="28" rx="4" fill="#1A1A2E" stroke="#111" stroke-width="2"/>
  <!-- Shoes -->
  <ellipse cx="45" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
  <ellipse cx="75" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
</svg>"""

_PLAYER_APPROVING = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160" width="120" height="160">
  <!-- Head -->
  <ellipse cx="60" cy="28" rx="22" ry="24" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="3"/>
  <!-- Hair -->
  <ellipse cx="60" cy="10" rx="22" ry="10" fill="#2C1810" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Eyes — wide, happy -->
  <ellipse cx="52" cy="26" rx="3.5" ry="4" fill="#1A1A2E"/>
  <ellipse cx="68" cy="26" rx="3.5" ry="4" fill="#1A1A2E"/>
  <ellipse cx="53" cy="25" rx="1.2" ry="1.5" fill="white"/>
  <ellipse cx="69" cy="25" rx="1.2" ry="1.5" fill="white"/>
  <!-- Big smile -->
  <path d="M50 38 Q60 47 70 38" fill="none" stroke="#1A1A2E" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Rosy cheeks -->
  <ellipse cx="46" cy="36" rx="6" ry="4" fill="#E8A0A0" opacity="0.6"/>
  <ellipse cx="74" cy="36" rx="6" ry="4" fill="#E8A0A0" opacity="0.6"/>
  <!-- Neck -->
  <rect x="54" y="50" width="12" height="10" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Body / suit jacket -->
  <path d="M25 68 Q30 56 54 60 L60 88 L66 60 Q90 56 95 68 L98 128 L22 128 Z" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="2"/>
  <!-- White shirt -->
  <path d="M54 60 L58 88 L62 88 L66 60 L60 66 Z" fill="white" stroke="#CCCCCC" stroke-width="1"/>
  <!-- Red tie -->
  <path d="M58 62 L56 80 L60 86 L64 80 L62 62 Z" fill="#C0392B" stroke="#922B21" stroke-width="1.5"/>
  <!-- Left arm — raised in victory -->
  <path d="M25 68 L5 45 L12 38 L32 62" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="3" stroke-linejoin="round"/>
  <!-- Left hand / fist up -->
  <ellipse cx="8" cy="41" rx="7" ry="7" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Right arm — raised in victory -->
  <path d="M95 68 L115 45 L108 38 L88 62" fill="#1A1A2E" stroke="#1A1A2E" stroke-width="3" stroke-linejoin="round"/>
  <!-- Right hand / fist up -->
  <ellipse cx="112" cy="41" rx="7" ry="7" fill="#F5CBA7" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Legs -->
  <rect x="35" y="126" width="20" height="30" rx="4" fill="#1A1A2E" stroke="#111" stroke-width="2"/>
  <rect x="65" y="126" width="20" height="30" rx="4" fill="#1A1A2E" stroke="#111" stroke-width="2"/>
  <!-- Shoes -->
  <ellipse cx="45" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
  <ellipse cx="75" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
</svg>"""

# ---------------------------------------------------------------------------
# Coach SVGs — measured evaluator, grey suit, glasses, clipboard
# ---------------------------------------------------------------------------

_COACH_STERN = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160" width="120" height="160">
  <!-- Head -->
  <ellipse cx="60" cy="30" rx="21" ry="23" fill="#F0D9C0" stroke="#1A1A2E" stroke-width="3"/>
  <!-- Hair — salt and pepper -->
  <ellipse cx="60" cy="13" rx="21" ry="9" fill="#888888" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Glasses frame -->
  <rect x="44" y="26" width="13" height="9" rx="3" fill="none" stroke="#1A1A2E" stroke-width="2"/>
  <rect x="63" y="26" width="13" height="9" rx="3" fill="none" stroke="#1A1A2E" stroke-width="2"/>
  <line x1="57" y1="30" x2="63" y2="30" stroke="#1A1A2E" stroke-width="2"/>
  <line x1="44" y1="30" x2="38" y2="29" stroke="#1A1A2E" stroke-width="2"/>
  <line x1="76" y1="30" x2="82" y2="29" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Eyes behind glasses -->
  <ellipse cx="50" cy="30" rx="2.5" ry="3" fill="#1A1A2E"/>
  <ellipse cx="69" cy="30" rx="2.5" ry="3" fill="#1A1A2E"/>
  <!-- Stern brow -->
  <path d="M45 24 Q50 22 57 24" fill="none" stroke="#1A1A2E" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M63 24 Q68 22 75 24" fill="none" stroke="#1A1A2E" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Flat stern mouth -->
  <line x1="52" y1="41" x2="68" y2="41" stroke="#1A1A2E" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Neck -->
  <rect x="54" y="51" width="12" height="10" fill="#F0D9C0" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Grey suit body -->
  <path d="M22 70 Q28 58 54 62 L60 92 L66 62 Q92 58 98 70 L102 130 L18 130 Z" fill="#5D6D7E" stroke="#1A1A2E" stroke-width="2.5"/>
  <!-- Shirt + tie -->
  <path d="M54 62 L57 90 L63 90 L66 62 L60 68 Z" fill="white" stroke="#CCC" stroke-width="1"/>
  <path d="M58 65 L57 80 L60 85 L63 80 L62 65 Z" fill="#7D6608" stroke="#5D4E08" stroke-width="1.5"/>
  <!-- Arms crossed — left over right -->
  <path d="M22 70 L18 95 L60 105 L65 95" fill="none" stroke="#5D6D7E" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>
  <!-- Right arm crossing under -->
  <path d="M98 70 L102 95 L55 105" fill="none" stroke="#4A5568" stroke-width="14" stroke-linecap="round" stroke-linejoin="round"/>
  <!-- Hands -->
  <ellipse cx="65" cy="96" rx="8" ry="7" fill="#F0D9C0" stroke="#1A1A2E" stroke-width="2"/>
  <ellipse cx="55" cy="106" rx="8" ry="7" fill="#F0D9C0" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Clipboard tucked under right arm -->
  <rect x="88" y="78" width="20" height="28" rx="3" fill="#D4AC0D" stroke="#1A1A2E" stroke-width="2"/>
  <rect x="90" y="82" width="16" height="3" rx="1" fill="#1A1A2E" opacity="0.5"/>
  <rect x="90" y="88" width="16" height="2" rx="1" fill="#1A1A2E" opacity="0.5"/>
  <rect x="90" y="93" width="12" height="2" rx="1" fill="#1A1A2E" opacity="0.5"/>
  <rect x="96" y="74" width="8" height="6" rx="2" fill="#888" stroke="#1A1A2E" stroke-width="1.5"/>
  <!-- Legs -->
  <rect x="33" y="128" width="22" height="28" rx="4" fill="#5D6D7E" stroke="#111" stroke-width="2"/>
  <rect x="65" y="128" width="22" height="28" rx="4" fill="#5D6D7E" stroke="#111" stroke-width="2"/>
  <!-- Shoes -->
  <ellipse cx="44" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
  <ellipse cx="76" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
</svg>"""

_COACH_APPROVING = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 160" width="120" height="160">
  <!-- Head -->
  <ellipse cx="60" cy="30" rx="21" ry="23" fill="#F0D9C0" stroke="#1A1A2E" stroke-width="3"/>
  <!-- Hair -->
  <ellipse cx="60" cy="13" rx="21" ry="9" fill="#888888" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Glasses -->
  <rect x="44" y="26" width="13" height="9" rx="3" fill="none" stroke="#1A1A2E" stroke-width="2"/>
  <rect x="63" y="26" width="13" height="9" rx="3" fill="none" stroke="#1A1A2E" stroke-width="2"/>
  <line x1="57" y1="30" x2="63" y2="30" stroke="#1A1A2E" stroke-width="2"/>
  <line x1="44" y1="30" x2="38" y2="29" stroke="#1A1A2E" stroke-width="2"/>
  <line x1="76" y1="30" x2="82" y2="29" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Eyes -->
  <ellipse cx="50" cy="30" rx="2.5" ry="3" fill="#1A1A2E"/>
  <ellipse cx="69" cy="30" rx="2.5" ry="3" fill="#1A1A2E"/>
  <!-- Slight smile brows -->
  <path d="M45 24 Q50 23 57 25" fill="none" stroke="#1A1A2E" stroke-width="2" stroke-linecap="round"/>
  <path d="M63 25 Q68 23 75 24" fill="none" stroke="#1A1A2E" stroke-width="2" stroke-linecap="round"/>
  <!-- Slight smile -->
  <path d="M52 41 Q60 46 68 41" fill="none" stroke="#1A1A2E" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Neck -->
  <rect x="54" y="51" width="12" height="10" fill="#F0D9C0" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Grey suit body -->
  <path d="M22 70 Q28 58 54 62 L60 92 L66 62 Q92 58 98 70 L102 130 L18 130 Z" fill="#5D6D7E" stroke="#1A1A2E" stroke-width="2.5"/>
  <!-- Shirt + tie -->
  <path d="M54 62 L57 90 L63 90 L66 62 L60 68 Z" fill="white" stroke="#CCC" stroke-width="1"/>
  <path d="M58 65 L57 80 L60 85 L63 80 L62 65 Z" fill="#7D6608" stroke="#5D4E08" stroke-width="1.5"/>
  <!-- Left arm — relaxed, lowered -->
  <path d="M22 70 L15 100 L24 104 L34 78" fill="#5D6D7E" stroke="#1A1A2E" stroke-width="3" stroke-linejoin="round"/>
  <!-- Left hand — open -->
  <ellipse cx="19" cy="102" rx="8" ry="7" fill="#F0D9C0" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Right arm — lowered, clipboard visible -->
  <path d="M98 70 L105 100 L96 104 L86 78" fill="#5D6D7E" stroke="#1A1A2E" stroke-width="3" stroke-linejoin="round"/>
  <!-- Right hand holding clipboard at side -->
  <ellipse cx="101" cy="102" rx="8" ry="7" fill="#F0D9C0" stroke="#1A1A2E" stroke-width="2"/>
  <!-- Clipboard — lowered to side -->
  <rect x="96" y="90" width="20" height="28" rx="3" fill="#D4AC0D" stroke="#1A1A2E" stroke-width="2"/>
  <rect x="98" y="94" width="16" height="3" rx="1" fill="#1A1A2E" opacity="0.5"/>
  <rect x="98" y="100" width="16" height="2" rx="1" fill="#1A1A2E" opacity="0.5"/>
  <rect x="98" y="105" width="12" height="2" rx="1" fill="#1A1A2E" opacity="0.5"/>
  <rect x="104" y="86" width="8" height="6" rx="2" fill="#888" stroke="#1A1A2E" stroke-width="1.5"/>
  <!-- Legs -->
  <rect x="33" y="128" width="22" height="28" rx="4" fill="#5D6D7E" stroke="#111" stroke-width="2"/>
  <rect x="65" y="128" width="22" height="28" rx="4" fill="#5D6D7E" stroke="#111" stroke-width="2"/>
  <!-- Shoes -->
  <ellipse cx="44" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
  <ellipse cx="76" cy="157" rx="14" ry="5" fill="#0D0D0D" stroke="#000" stroke-width="1.5"/>
</svg>"""

# ---------------------------------------------------------------------------
# Public dicts and render helper
# ---------------------------------------------------------------------------

PLAYER_SVGS: dict[str, str] = {
    "confident": _PLAYER_CONFIDENT,
    "deflated": _PLAYER_DEFLATED,
    "approving": _PLAYER_APPROVING,
}

COACH_SVGS: dict[str, str] = {
    "stern": _COACH_STERN,
    "approving": _COACH_APPROVING,
}


def render_character(svgs: dict[str, str], state: str, label: str) -> None:
    svg = svgs.get(state, next(iter(svgs.values())))
    st.markdown(
        f"""<div style="text-align:center">{svg}
        <div style="font-weight:700;font-size:0.85rem;
                    letter-spacing:0.05em;margin-top:4px">
            {label}
        </div></div>""",
        unsafe_allow_html=True,
    )
