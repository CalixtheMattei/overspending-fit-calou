/**
 * Default seasonal cover images for Moments.
 * Each SVG is a 1200×400 illustration that gets auto-assigned based on the
 * start date's month when creating a new moment without an explicit cover.
 *
 * Season mapping:
 *   Winter  — Dec (12), Jan (1), Feb (2)
 *   Spring  — Mar (3)  – May (5)
 *   Summer  — Jun (6)  – Aug (8)
 *   Autumn  — Sep (9)  – Nov (11)
 */

const COVER_WINTER = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.3" y2="1">
      <stop offset="0%" stop-color="#0a0e1a"/>
      <stop offset="45%" stop-color="#1a2744"/>
      <stop offset="100%" stop-color="#14532d"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef3c7" stop-opacity="0.7"/>
      <stop offset="50%" stop-color="#fde68a" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#fde68a" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="400" fill="url(#bg)"/>
  <ellipse cx="600" cy="0" rx="500" ry="200" fill="#1e3a5f" opacity="0.5"/>
  <g fill="#f0f9ff" opacity="0.7">
    <circle cx="80"  cy="40"  r="1.5"/>
    <circle cx="200" cy="20"  r="1"/>
    <circle cx="350" cy="55"  r="1.5"/>
    <circle cx="420" cy="15"  r="1"/>
    <circle cx="530" cy="70"  r="1"/>
    <circle cx="680" cy="30"  r="1.5"/>
    <circle cx="760" cy="60"  r="1"/>
    <circle cx="870" cy="25"  r="1.5"/>
    <circle cx="950" cy="50"  r="1"/>
    <circle cx="1050" cy="35" r="1.5"/>
    <circle cx="1120" cy="70" r="1"/>
    <circle cx="150" cy="90"  r="1"/>
    <circle cx="470" cy="100" r="1.5"/>
    <circle cx="790" cy="85"  r="1"/>
    <circle cx="1000" cy="95" r="1.5"/>
  </g>
  <ellipse cx="600" cy="60" rx="120" ry="120" fill="url(#glow)"/>
  <g transform="translate(600, 60)">
    <polygon points="0,-36 4,-10 18,-18 10,-4 36,0 10,4 18,18 4,10 0,36 -4,10 -18,18 -10,4 -36,0 -10,-4 -18,-18 -4,-10" fill="#fef9c3" opacity="0.95"/>
    <circle cx="0" cy="0" r="5" fill="#ffffff"/>
  </g>
  <g fill="#0f3d1a" opacity="0.85">
    <polygon points="60,380 120,200 180,380"/>
    <polygon points="100,380 160,240 220,380"/>
    <polygon points="0,380 50,260 100,380"/>
  </g>
  <g fill="#0f3d1a" opacity="0.85">
    <polygon points="1020,380 1080,200 1140,380"/>
    <polygon points="1060,380 1120,240 1180,380"/>
    <polygon points="980,380 1030,260 1080,380"/>
  </g>
  <path d="M0,370 Q200,355 400,365 Q600,375 800,362 Q1000,350 1200,368 L1200,400 L0,400 Z" fill="#e0f2fe" opacity="0.9"/>
  <path d="M0,380 Q300,370 600,378 Q900,386 1200,375 L1200,400 L0,400 Z" fill="#f0f9ff" opacity="0.95"/>
  <g fill="#f0f9ff" opacity="0.7">
    <circle cx="120" cy="200" r="5"/>
    <circle cx="160" cy="240" r="4"/>
    <circle cx="1080" cy="200" r="5"/>
    <circle cx="1120" cy="240" r="4"/>
  </g>
  <g stroke="#e0f2fe" stroke-width="1" opacity="0.25">
    <g transform="translate(300, 150)">
      <line x1="-20" y1="0" x2="20" y2="0"/>
      <line x1="0" y1="-20" x2="0" y2="20"/>
      <line x1="-14" y1="-14" x2="14" y2="14"/>
      <line x1="14" y1="-14" x2="-14" y2="14"/>
    </g>
    <g transform="translate(900, 180)">
      <line x1="-15" y1="0" x2="15" y2="0"/>
      <line x1="0" y1="-15" x2="0" y2="15"/>
      <line x1="-11" y1="-11" x2="11" y2="11"/>
      <line x1="11" y1="-11" x2="-11" y2="11"/>
    </g>
    <g transform="translate(550, 220)">
      <line x1="-12" y1="0" x2="12" y2="0"/>
      <line x1="0" y1="-12" x2="0" y2="12"/>
      <line x1="-8" y1="-8" x2="8" y2="8"/>
      <line x1="8" y1="-8" x2="-8" y2="8"/>
    </g>
  </g>
</svg>`;

const COVER_SPRING = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#bae6fd"/>
      <stop offset="55%" stop-color="#d1fae5"/>
      <stop offset="100%" stop-color="#86efac"/>
    </linearGradient>
    <radialGradient id="sun" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef9c3"/>
      <stop offset="60%" stop-color="#fde68a" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#fde68a" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="400" fill="url(#bg)"/>
  <circle cx="230" cy="115" r="120" fill="#fef3c7" opacity="0.4"/>
  <circle cx="230" cy="115" r="55" fill="url(#sun)"/>
  <g stroke="#fde68a" stroke-width="1.5" opacity="0.3">
    <line x1="230" y1="40"  x2="230" y2="15"/>
    <line x1="230" y1="190" x2="230" y2="215"/>
    <line x1="155" y1="115" x2="130" y2="115"/>
    <line x1="305" y1="115" x2="330" y2="115"/>
    <line x1="177" y1="62"  x2="159" y2="44"/>
    <line x1="283" y1="168" x2="301" y2="186"/>
    <line x1="283" y1="62"  x2="301" y2="44"/>
    <line x1="177" y1="168" x2="159" y2="186"/>
  </g>
  <g fill="white" opacity="0.65">
    <ellipse cx="700" cy="75" rx="90" ry="34"/>
    <ellipse cx="775" cy="60" rx="60" ry="38"/>
    <ellipse cx="635" cy="70" rx="50" ry="28"/>
    <ellipse cx="430" cy="105" rx="70" ry="28"/>
    <ellipse cx="490" cy="90" rx="50" ry="32"/>
    <ellipse cx="950" cy="90" rx="75" ry="30"/>
    <ellipse cx="1010" cy="75" rx="55" ry="34"/>
  </g>
  <path d="M0,310 Q300,288 600,308 Q900,328 1200,305 L1200,400 L0,400 Z" fill="#4ade80" opacity="0.65"/>
  <path d="M0,345 Q400,328 800,342 Q1000,349 1200,332 L1200,400 L0,400 Z" fill="#22c55e" opacity="0.8"/>
  <g fill="#fde68a" opacity="0.9">
    <circle cx="130" cy="340" r="5"/>
    <circle cx="280" cy="332" r="4"/>
    <circle cx="430" cy="344" r="5"/>
    <circle cx="590" cy="336" r="4"/>
    <circle cx="740" cy="342" r="5"/>
    <circle cx="895" cy="334" r="4"/>
    <circle cx="1060" cy="340" r="5"/>
  </g>
  <g fill="#f9a8d4" opacity="0.85">
    <circle cx="210" cy="347" r="4"/>
    <circle cx="360" cy="338" r="4"/>
    <circle cx="510" cy="350" r="4"/>
    <circle cx="665" cy="341" r="4"/>
    <circle cx="820" cy="347" r="4"/>
    <circle cx="975" cy="339" r="4"/>
    <circle cx="1140" cy="345" r="4"/>
  </g>
</svg>`;

const COVER_SUMMER = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0c4a6e"/>
      <stop offset="55%" stop-color="#0ea5e9"/>
      <stop offset="100%" stop-color="#f59e0b"/>
    </linearGradient>
    <radialGradient id="sun" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fde68a" stop-opacity="1"/>
      <stop offset="60%" stop-color="#f59e0b" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#f59e0b" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef3c7" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#fef3c7" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0284c7"/>
      <stop offset="100%" stop-color="#075985"/>
    </linearGradient>
    <linearGradient id="sand" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#fde68a"/>
      <stop offset="100%" stop-color="#d97706"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="400" fill="url(#bg)"/>
  <circle cx="900" cy="150" r="180" fill="url(#glow)"/>
  <circle cx="900" cy="150" r="80" fill="url(#sun)"/>
  <g stroke="#fde68a" stroke-width="2" opacity="0.35">
    <line x1="900" y1="50"  x2="900" y2="20"/>
    <line x1="900" y1="250" x2="900" y2="280"/>
    <line x1="800" y1="150" x2="770" y2="150"/>
    <line x1="1000" y1="150" x2="1030" y2="150"/>
    <line x1="829" y1="79"  x2="808" y2="58"/>
    <line x1="971" y1="221" x2="992" y2="242"/>
    <line x1="971" y1="79"  x2="992" y2="58"/>
    <line x1="829" y1="221" x2="808" y2="242"/>
  </g>
  <rect x="0" y="280" width="1200" height="120" fill="url(#sea)"/>
  <path d="M0,280 Q150,265 300,280 Q450,295 600,280 Q750,265 900,280 Q1050,295 1200,280 L1200,400 L0,400 Z" fill="#0369a1" opacity="0.6"/>
  <path d="M0,295 Q200,282 400,295 Q600,308 800,295 Q1000,282 1200,295 L1200,400 L0,400 Z" fill="#075985" opacity="0.5"/>
  <path d="M0,350 Q300,335 600,350 Q900,365 1200,350 L1200,400 L0,400 Z" fill="url(#sand)" opacity="0.9"/>
  <line x1="0" y1="280" x2="1200" y2="280" stroke="#bae6fd" stroke-width="1" opacity="0.4"/>
</svg>`;

const COVER_AUTUMN = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#431407"/>
      <stop offset="40%" stop-color="#c2410c"/>
      <stop offset="100%" stop-color="#f59e0b"/>
    </linearGradient>
    <radialGradient id="sun" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fde68a"/>
      <stop offset="60%" stop-color="#f97316" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#f97316" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="400" fill="url(#bg)"/>
  <circle cx="950" cy="195" r="150" fill="url(#sun)"/>
  <path d="M0,330 Q300,312 600,326 Q900,340 1200,322 L1200,400 L0,400 Z" fill="#7c2d12" opacity="0.8"/>
  <path d="M0,358 Q400,342 800,354 Q1000,360 1200,348 L1200,400 L0,400 Z" fill="#431407" opacity="0.9"/>
  <rect x="92" y="180" width="10" height="155" fill="#1c0a00"/>
  <ellipse cx="97" cy="168" rx="62" ry="72" fill="#c2410c" opacity="0.9"/>
  <ellipse cx="76" cy="174" rx="42" ry="52" fill="#ea580c" opacity="0.7"/>
  <ellipse cx="118" cy="180" rx="46" ry="56" fill="#b45309" opacity="0.7"/>
  <rect x="1098" y="180" width="10" height="155" fill="#1c0a00"/>
  <ellipse cx="1103" cy="168" rx="62" ry="72" fill="#c2410c" opacity="0.9"/>
  <ellipse cx="1082" cy="174" rx="42" ry="52" fill="#ea580c" opacity="0.7"/>
  <ellipse cx="1124" cy="180" rx="46" ry="56" fill="#b45309" opacity="0.7"/>
  <g fill="#f97316" opacity="0.6">
    <ellipse cx="290" cy="148" rx="8" ry="5" transform="rotate(-30 290 148)"/>
    <ellipse cx="440" cy="195" rx="7" ry="4" transform="rotate(20 440 195)"/>
    <ellipse cx="590" cy="128" rx="8" ry="5" transform="rotate(-15 590 128)"/>
    <ellipse cx="720" cy="175" rx="7" ry="4" transform="rotate(40 720 175)"/>
    <ellipse cx="510" cy="258" rx="8" ry="5" transform="rotate(-25 510 258)"/>
    <ellipse cx="380" cy="300" rx="7" ry="4" transform="rotate(12 380 300)"/>
    <ellipse cx="670" cy="285" rx="8" ry="5" transform="rotate(-35 670 285)"/>
  </g>
  <g fill="#fbbf24" opacity="0.5">
    <ellipse cx="340" cy="218" rx="7" ry="4" transform="rotate(15 340 218)"/>
    <ellipse cx="640" cy="248" rx="8" ry="5" transform="rotate(-40 640 248)"/>
    <ellipse cx="810" cy="138" rx="6" ry="4" transform="rotate(25 810 138)"/>
    <ellipse cx="470" cy="320" rx="7" ry="4" transform="rotate(-10 470 320)"/>
    <ellipse cx="760" cy="310" rx="8" ry="5" transform="rotate(30 760 310)"/>
  </g>
</svg>`;

const COVER_SPORTS = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#0c1a3a"/>
      <stop offset="45%" stop-color="#1d4ed8"/>
      <stop offset="100%" stop-color="#60a5fa"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="400" fill="url(#bg)"/>
  <g fill="#f0f9ff" opacity="0.5">
    <circle cx="60"   cy="35"  r="1.5"/>
    <circle cx="180"  cy="55"  r="1"/>
    <circle cx="320"  cy="20"  r="1.5"/>
    <circle cx="480"  cy="48"  r="1"/>
    <circle cx="700"  cy="28"  r="1.5"/>
    <circle cx="860"  cy="52"  r="1"/>
    <circle cx="1020" cy="18"  r="1.5"/>
    <circle cx="1160" cy="42"  r="1"/>
  </g>
  <polygon points="0,310 220,95 440,310"    fill="#1e3a5f" opacity="0.75"/>
  <polygon points="320,310 600,65 880,310"  fill="#1e3a5f" opacity="0.75"/>
  <polygon points="760,310 1010,110 1260,310" fill="#1e3a5f" opacity="0.70"/>
  <polygon points="220,95  190,148 250,148" fill="#e0f2fe" opacity="0.9"/>
  <polygon points="600,65  558,128 642,128" fill="#e0f2fe" opacity="0.9"/>
  <polygon points="1010,110 972,162 1048,162" fill="#e0f2fe" opacity="0.9"/>
  <polygon points="-60,400 180,175 420,400"  fill="#0f172a" opacity="0.9"/>
  <polygon points="300,400 580,150 860,400"  fill="#172554" opacity="0.85"/>
  <polygon points="720,400 980,195 1240,400" fill="#0f172a" opacity="0.9"/>
  <path d="M0,375 Q300,358 600,372 Q900,386 1200,368 L1200,400 L0,400 Z" fill="#14532d" opacity="0.65"/>
  <path d="M555,400 Q572,368 588,342 Q605,316 628,285 Q648,258 672,232"
        stroke="#fde68a" stroke-width="2" fill="none" opacity="0.45" stroke-dasharray="7,5"/>
</svg>`;

const COVER_CULTURE = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#09090f"/>
      <stop offset="55%" stop-color="#1e1b4b"/>
      <stop offset="100%" stop-color="#312e81"/>
    </linearGradient>
    <radialGradient id="moon" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef9c3" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#fef9c3" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="400" fill="url(#bg)"/>
  <g fill="#f0f9ff" opacity="0.45">
    <circle cx="90"   cy="28"  r="1"/>
    <circle cx="220"  cy="48"  r="1.5"/>
    <circle cx="370"  cy="18"  r="1"/>
    <circle cx="510"  cy="38"  r="1.5"/>
    <circle cx="660"  cy="12"  r="1"/>
    <circle cx="800"  cy="42"  r="1.5"/>
    <circle cx="940"  cy="24"  r="1"/>
    <circle cx="1080" cy="50"  r="1.5"/>
    <circle cx="1170" cy="30"  r="1"/>
  </g>
  <circle cx="165" cy="85" r="75" fill="url(#moon)"/>
  <circle cx="165" cy="85" r="30" fill="#fef9c3" opacity="0.88"/>
  <g fill="#1a1744" opacity="0.9">
    <rect x="0"    y="255" width="55"  height="145"/>
    <rect x="70"   y="225" width="48"  height="175"/>
    <rect x="135"  y="245" width="38"  height="155"/>
    <rect x="188"  y="200" width="68"  height="200"/>
    <rect x="272"  y="235" width="52"  height="165"/>
    <rect x="340"  y="215" width="44"  height="185"/>
    <rect x="398"  y="182" width="78"  height="218"/>
    <rect x="492"  y="232" width="48"  height="168"/>
    <rect x="556"  y="198" width="62"  height="202"/>
    <rect x="634"  y="218" width="54"  height="182"/>
    <rect x="704"  y="202" width="58"  height="198"/>
    <rect x="778"  y="228" width="44"  height="172"/>
    <rect x="836"  y="188" width="72"  height="212"/>
    <rect x="924"  y="212" width="48"  height="188"/>
    <rect x="988"  y="238" width="38"  height="162"/>
    <rect x="1042" y="208" width="72"  height="192"/>
    <rect x="1130" y="222" width="70"  height="178"/>
  </g>
  <g fill="#09090f" opacity="0.95">
    <rect x="0"    y="292" width="76"  height="108"/>
    <rect x="96"   y="272" width="58"  height="128"/>
    <rect x="174"  y="288" width="88"  height="112"/>
    <rect x="280"  y="262" width="68"  height="138"/>
    <rect x="368"  y="276" width="82"  height="124"/>
    <rect x="474"  y="258" width="72"  height="142"/>
    <rect x="570"  y="268" width="96"  height="132"/>
    <rect x="690"  y="252" width="78"  height="148"/>
    <rect x="792"  y="272" width="68"  height="128"/>
    <rect x="882"  y="256" width="92"  height="144"/>
    <rect x="998"  y="270" width="76"  height="130"/>
    <rect x="1098" y="262" width="102" height="138"/>
  </g>
  <g fill="#fde68a" opacity="0.65">
    <rect x="88"  y="232" width="3" height="4"/>
    <rect x="96"  y="244" width="3" height="4"/>
    <rect x="204" y="208" width="3" height="4"/>
    <rect x="218" y="220" width="3" height="4"/>
    <rect x="234" y="210" width="3" height="4"/>
    <rect x="414" y="192" width="3" height="4"/>
    <rect x="428" y="204" width="3" height="4"/>
    <rect x="444" y="194" width="3" height="4"/>
    <rect x="568" y="208" width="3" height="4"/>
    <rect x="580" y="220" width="3" height="4"/>
    <rect x="718" y="212" width="3" height="4"/>
    <rect x="732" y="224" width="3" height="4"/>
    <rect x="854" y="198" width="3" height="4"/>
    <rect x="868" y="210" width="3" height="4"/>
    <rect x="884" y="200" width="3" height="4"/>
    <rect x="1055" y="218" width="3" height="4"/>
    <rect x="1070" y="228" width="3" height="4"/>
  </g>
  <path d="M0,362 Q600,354 1200,362 L1200,400 L0,400 Z" fill="#09090f" opacity="0.6"/>
</svg>`;

const svgToDataUri = (svg: string): string =>
    `data:image/svg+xml;base64,${btoa(svg)}`;

// Keyword lists used for name-based matching. Checked in order; first match wins.
// Normalisation: input is lowercased and accents are stripped before matching.
const KEYWORDS: { cover: string; terms: string[] }[] = [
    {
        cover: "sports",
        terms: [
            "sport", "sports",
            "running", "course a pied", "course à pied",
            "trail", "hike", "hiking", "randonnee", "randonnée", "rando",
            "velo", "vélo", "cyclisme", "cycling", "bike",
            "marathon", "triathlon", "ironman",
            "fitness", "gym", "crossfit",
            "match", "tournoi", "tournament",
            "football", "tennis", "golf", "natation", "swimming",
            "escalade", "climbing",
        ],
    },
    {
        cover: "culture",
        terms: [
            "musee", "musée", "museum",
            "concert", "festival",
            "expo", "exposition", "exhibition",
            "theatre", "théâtre", "theater",
            "cinema", "cinéma",
            "opera", "opéra",
            "culture", "culturel",
            "art", "galerie", "gallery",
            "spectacle", "visite",
        ],
    },
    {
        cover: "winter",
        terms: [
            "christmas", "xmas", "noel", "noël", "nöel",
            "ski", "snow", "neige", "snowboard",
            "hiver", "winter",
            "saint-nicolas", "saint nicolas",
        ],
    },
    {
        cover: "summer",
        terms: [
            "summer", "ete", "été",
            "beach", "plage", "mer", "sea", "ocean",
            "vacances", "vacation", "holiday", "holidays",
            "soleil",
        ],
    },
    {
        cover: "spring",
        terms: [
            "spring", "printemps",
            "flower", "fleur", "fleurs",
            "easter", "paques", "pâques",
        ],
    },
    {
        cover: "autumn",
        terms: [
            "autumn", "fall", "automne",
            "harvest", "vendange", "vendanges",
        ],
    },
];

const COVER_BY_KEY: Record<string, string> = {
    sports: COVER_SPORTS,
    culture: COVER_CULTURE,
    winter: COVER_WINTER,
    spring: COVER_SPRING,
    summer: COVER_SUMMER,
    autumn: COVER_AUTUMN,
};

/** Normalise a string: lowercase + strip common accents so "été" matches "ete". */
const normalise = (s: string) =>
    s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

/** Pick a cover key from the moment name, or null if no keyword matched. */
const coverKeyFromName = (name: string): string | null => {
    const n = normalise(name);
    for (const { cover, terms } of KEYWORDS) {
        if (terms.some((t) => n.includes(normalise(t)))) return cover;
    }
    return null;
};

/** Pick a cover key from the start-date month, or null if date is missing/invalid. */
const coverKeyFromDate = (startDate: string): string | null => {
    if (!startDate) return null;
    const parsed = new Date(`${startDate}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return null;
    const m = parsed.getMonth() + 1; // 1-12
    if (m === 12 || m === 1 || m === 2) return "winter";
    if (m >= 3 && m <= 5) return "spring";
    if (m >= 6 && m <= 8) return "summer";
    return "autumn";
};

/**
 * Returns a base64 data URI for the best-matching default cover image.
 *
 * Resolution order:
 *   1. Name keyword match  (christmas → winter, vacances → summer, …)
 *   2. Start-date season   (Jun-Aug → summer, Dec-Feb → winter, …)
 *   3. Hard fallback       (summer)
 */
export const getDefaultMomentCoverDataUri = (name: string, startDate: string): string => {
    const key = coverKeyFromName(name) ?? coverKeyFromDate(startDate) ?? "summer";
    return svgToDataUri(COVER_BY_KEY[key]);
};
