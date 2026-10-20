# -*- coding: utf-8 -*-
"""Parsing of SNUH drug product names (일반성분명) into ingredients, route and exclusion flags, for the P2 drug map.

Adapted from the CKD_ML study's `Code/SNUHUB/drug_dictionary.py` (same author; audited there against the 7,649 distinct names of the
extract). The name parsing is taken over with three changes: the noise patterns ignore case ('10만U/ml', '1000IU'), a trailing strength
('Atorvastatin 10/5mg') and a '+' between ingredients are handled, and the ingredient name is matched in stages (full name first, salt
words stripped later) so that 'potassium chloride' does not collapse into 'chloride'. The vocabulary matching is in p2_build_maps.py.
No patient data: the input is a product name.

  parse(name)        -> dict(ingredients, salt, dose_form, route, is_investigational, is_fluid, is_topical, exclude_reason)
  candidates(ing)    -> keys to try, most specific first, for matching an ingredient with RxNorm ingredient names
  clean(s)           -> key of a vocabulary concept name
"""
import re

# ── dose form -> route: the last form keyword found in the whole name wins ('Atorvastatin 10mg tab Korea', ...) ──
DOSE_FORM_ROUTE = [
    (r'\bgargle\b', 'gargle', 'gargle'),
    (r'\boph\b|\beye\s*drop|\bophthalmic\b', 'oph', 'ophthalmic'),
    (r'\botic\b|\bear\s*drop', 'otic', 'otic'),
    (r'\bnasal\b|\bnas\b', 'nasal', 'nasal'),
    (r'\binhaler\b|\bneb\b|\brespule\b|\bturbuhaler\b|\bdiskus\b|\bevohaler\b|\bhandihaler\b', 'inhaler', 'inhalation'),
    (r'\bsupp\b|\bsuppository\b|\benema\b', 'supp', 'rectal'),
    (r'\birrigation\b|\bflushing\b', 'irrigation', 'irrigation'),
    (r'\bointment\b|\boint\b|\bcream\b|\blotion\b|\bgel\b|\bpatch\b|\bplaster\b|\bshampoo\b|\bfoam\b', 'topical', 'topical'),
    (r'\bpfs\b|\bsrg\b|\bsyringe\b|\bprefilled\b', 'PFS', 'parenteral'),
    (r'\bpen\b|\bsolostar\b|\bflexpen\b|\bkwikpen\b|\bquickpen\b', 'pen', 'parenteral'),
    (r'\binj\b|\bamp\b|\bvia\b|\bvial\b|\binjection\b', 'inj', 'parenteral'),
    (r'\bbag\b|\bbtl\b|\bbottle\b', 'bag', 'parenteral'),
    (r'\bsyrup\b|\bsuspension\b|\bsusp\b|\bliquid\b|\bliq\b|\bsolution\s*\(oral\)|\bjelly\b', 'syrup', 'oral'),
    (r'\bgranule\b|\bpkg\b|\bpowder\b|\bpower\b|\bsachet\b|\boral\s+drops?\b', 'granule', 'oral'),   # 'power' = frequent typo of powder
    (r'\bcap\b|\bcapsule\b', 'cap', 'oral'),
    (r'\btroche\b|\blozenge\b', 'troche', 'oral'),
    (r'\btab\b|\btablet\b|\bpil\b|\bpill\b', 'tab', 'oral'),
]

# infusion fluids, dialysates, irrigation fluids: not a pharmacological exposure
FLUID_PAT = (r'normal saline|\bn/?s\b|dextrose|\bd/?w\b|hartmann|ringer|plasma solution|'
             r'sterile water|water for injection|\btpn\b|amino acid|aminofluid|lipid emulsion|'
             r'smoflipid|intralipid|\bbss\b|peritoneal|perisis|dianeal|extraneal|nutrineal|'
             r'hemosol|phoxilium|prismasol|irrigation|flushing|heparin.*flush')
INVESTIGATIONAL_PAT = r'임상|placebo|위약'
TOPICAL_ROUTES = ('topical', 'ophthalmic', 'gargle', 'inhalation', 'otic', 'nasal')

_SALT_PAT = re.compile(
    r'\(-\s*([a-z][a-z\s]*?)\)'                      # Amlodipine(-besylate)
    r'|\b(hcl|hydrochloride|sodium|potassium|calcium|magnesium|besylate|maleate|tartrate|'
    r'succinate|fumarate|mesylate|sulfate|phosphate|acetate|citrate|carbonate|nitrate|'
    r'bromide|chloride|oxalate|malate|napadisilate|cilexitil|medoxomil|mofetil|'
    r'aceponate|furoate|propionate|valerate|dipropionate|axetil|trometamol|'
    r't-butylamine|erbumine|arginine|lysine|cilexetil)\b')

# what is cut off the ingredient part: dose form, strength, packaging, in-house tags (case-insensitive: '10만U/ml', '1000IU')
_TAIL_NOISE = re.compile(
    r'\s*\(.*?\)|\s*\[.*?\]|_.*$|\b\d+(?:[,.]\d+)?\s*'
    r'(?:mcg|mg|g|kg|ml|l|iu|u|unit|units|meq|mmol|%|dose|만u|만unit|만단위)(?![a-z])'
    r'.*$|\b(?:tab|cap|inj|bag|btl|syrup|granule|powder|pkg|oph|gargle|patch|cream|lotion|'
    r'ointment|gel|supp|inhaler|pen|pfs|srg|via|vial|amp|solution|suspension|susp|'
    r'sr|er|od|xr|cr|chewable|dispersible|enteric|coated|korea|kp|odt|lfdt|fdt)\b.*$', re.I)

# Korean hospital spelling and INN names -> the spelling RxNorm uses (whole key or word-prefix match on the cleaned name)
FIXES = {
    'prednisolon': 'prednisolone', 'cyclosporin': 'cyclosporine', 'ciclosporin': 'cyclosporine', 'indometacin': 'indomethacin',
    'chlortalidone': 'chlorthalidone', 'epoetin alpha': 'epoetin alfa', 'darbepoetin alpha': 'darbepoetin alfa',
    'pethidine': 'meperidine', 'paracetamol': 'acetaminophen', 'adrenaline': 'epinephrine', 'noradrenaline': 'norepinephrine',
    'salbutamol': 'albuterol', 'glyceryl trinitrate': 'nitroglycerin', 'rifampicin': 'rifampin', 'lignocaine': 'lidocaine',
    'udca': 'ursodiol', 'ursodeoxycholic acid': 'ursodiol', 'insulin human regular': 'insulin regular human',
    'phophate': 'phosphate', 'thioctic acid': 'thioctic acid amide', 'candesartan cilexitil': 'candesartan',
    'perindopril t-butylamine': 'perindopril', 'amlodipine besylate': 'amlodipine', 'atorvastatin calcium': 'atorvastatin',
    's-amlodipine': 'levamlodipine',
}
WORD_FIXES = {'phophate': 'phosphate', 'sulphate': 'sulfate', 'sulphite': 'sulfite'}      # typos / British spelling inside a name
SALT_WORDS = (r'hcl|hydrochloride|dihydrochloride|hydrobromide|sodium|disodium|potassium|dipotassium|calcium|besylate|maleate|tartrate|'
              r'succinate|fumarate|hemifumarate|mesylate|sulfate|phosphate|acetate|citrate|carbonate|mofetil|medoxomil|cilexitil|'
              r'axetil|cilexetil|trometamol|erbumine|t-butylamine|camsylate|bromide|chloride|nitrate|oxalate|malate|napadisilate|'
              r'propionate|dipropionate|furoate|valerate|monohydrate|dihydrate|trihydrate|hydrate|anhydrous|salt')
_SALT_RE = re.compile(r'\b(?:' + SALT_WORDS + r')\b')
_SALT_ABBR = re.compile(r'(?<=\w{4})\s+(?:k|ca|na|mg|zn)$')       # 'Losartan K', 'Pitavastatin Ca'


def clean(s):
    """Lower case, content of parentheses and punctuation removed, spaces collapsed."""
    s = str(s).lower().strip()
    s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r'[^a-z0-9\s-]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip(' -')


def _fix(k):
    k = ' '.join(WORD_FIXES.get(w, w) for w in k.split())
    for a, b in FIXES.items():
        if k == a or k.startswith(a + ' '):
            return b + k[len(a):]
    return k


def strip_salts(k):
    k = _SALT_RE.sub(' ', k)
    k = _SALT_ABBR.sub('', ' '.join(k.split()))
    return ' '.join(k.split())


def candidates(ing):
    """Keys to try for one ingredient string, most specific first: the cleaned name, the name after the spelling fixes, then without
    salt words (and fixed again)."""
    out = []
    for k in (clean(ing),):
        for v in (k, _fix(k), strip_salts(_fix(k)), _fix(strip_salts(_fix(k)))):
            if v and v not in out:
                out.append(v)
    return out


def find_dose_form(name_low):
    """(dose_form, route) from the last form keyword in the name; (None, 'unknown') if none."""
    s = re.sub(r'[_,()\[\]]', ' ', name_low)          # '_' is a word character: 'pen_1단위씩' would break \b
    best = None
    for pat, form, route in DOSE_FORM_ROUTE:
        for m in re.finditer(pat, s):
            if best is None or m.start() > best[0]:
                best = (m.start(), form, route)
    return (best[1], best[2]) if best else (None, 'unknown')


def extract_salt(name_low):
    m = _SALT_PAT.search(name_low)
    return (m.group(1) or m.group(2)).strip() if m else None


def extract_ingredients(name):
    """Ingredient part of a product name; a combination product is split at '/' or '+'. A brand product ('Brand* 10mg tab') gives the
    brand, which no vocabulary knows."""
    s = name
    if '*' in s:
        s = s.split('*')[0]
    s = re.sub(r'^\s*\(.*?\)\s*', '', s)                 # leading '(임상약)'
    s = _TAIL_NOISE.sub('', s).strip(' ,-/+')
    if not s:
        return []
    parts = [re.sub(r'[\s\d/.,\-]+$', '', p).strip(' ,-') for p in re.split(r'/|\+', s)]   # 'Atorvastatin 10/5mg' leaves '... 10/'
    return [p.lower() for p in parts if p and len(p) > 1]


def parse(name):
    name = str(name)
    low = name.lower()
    form, route = find_dose_form(low)
    inv = bool(re.search(INVESTIGATIONAL_PAT, low))
    fluid = bool(re.search(FLUID_PAT, low))
    topical = route in TOPICAL_ROUTES
    reasons = [r for r, f in (('investigational', inv), ('fluid', fluid), ('topical', topical)) if f]
    return {'ingredients': extract_ingredients(name), 'salt': extract_salt(low), 'dose_form': form, 'route': route,
            'is_investigational': inv, 'is_fluid': fluid, 'is_topical': topical,
            'exclude_reason': '|'.join(reasons) if reasons else ''}
