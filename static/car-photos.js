/**
 * Photo URLs for car models via Imagin Studio (studio renders).
 * Example: BMW 5 Series + F10 → 2014 5-series render.
 */
(function (global) {
  var MAKE_MAP = {
    'Mercedes-Benz': 'mercedes',
    'Land Rover': 'land-rover',
    'Great Wall': 'great-wall',
    'Li Auto': 'li',
    'Rolls-Royce': 'rolls-royce',
    'Aston Martin': 'aston-martin',
    'Alfa Romeo': 'alfa-romeo',
    'SsangYong': 'ssangyong',
    'Москвич': 'moskvich',
    Volkswagen: 'volkswagen',
    BMW: 'bmw',
    Toyota: 'toyota',
    Lada: 'lada',
    Kia: 'kia',
    Hyundai: 'hyundai',
    Audi: 'audi',
    Skoda: 'skoda',
    Renault: 'renault',
    Nissan: 'nissan',
    Mazda: 'mazda',
    Ford: 'ford',
    Chevrolet: 'chevrolet',
    Mitsubishi: 'mitsubishi',
    Lexus: 'lexus',
    Volvo: 'volvo',
    Porsche: 'porsche',
    Chery: 'chery',
    Haval: 'haval',
    Geely: 'geely',
    Honda: 'honda',
    Subaru: 'subaru',
    Tesla: 'tesla',
    Jeep: 'jeep',
    Genesis: 'genesis',
    Infiniti: 'infiniti',
    Mini: 'mini',
    Peugeot: 'peugeot',
    Citroen: 'citroen',
    Opel: 'opel',
    Suzuki: 'suzuki',
    UAZ: 'uaz',
    GAZ: 'gaz',
    Changan: 'changan',
    Tank: 'tank',
    BYD: 'byd',
    Zeekr: 'zeekr',
    Exeed: 'exeed',
    Omoda: 'omoda',
    Jaecoo: 'jaecoo'
  };

  var FAMILY_MAP = {
    '1 Series': '1',
    '2 Series': '2',
    '3 Series': '3',
    '4 Series': '4',
    '5 Series': '5',
    '6 Series': '6',
    '7 Series': '7',
    '8 Series': '8',
    'A-Class': 'a-class',
    'B-Class': 'b-class',
    'C-Class': 'c-class',
    'E-Class': 'e-class',
    'S-Class': 's-class',
    'G-Class': 'g-class',
    'Land Cruiser Prado': 'land-cruiser-prado',
    'Land Cruiser': 'land-cruiser',
    'Range Rover Sport': 'range-rover-sport',
    'Range Rover Velar': 'range-rover-velar',
    'Range Rover Evoque': 'range-rover-evoque',
    'Range Rover': 'range-rover',
    'Santa Fe': 'santa-fe',
    'Grand Cherokee': 'grand-cherokee'
  };

  var CHASSIS_YEAR = {
    F10: 2014, F11: 2014, F30: 2014, F32: 2015, F15: 2015, F25: 2015, F20: 2015, F01: 2013,
    G30: 2019, G31: 2019, G20: 2020, G11: 2018, G05: 2020, G01: 2019, G22: 2021, G70: 2023,
    E60: 2008, E90: 2008, E70: 2010, E46: 2004,
    W204: 2012, W205: 2017, W206: 2022, W212: 2014, W213: 2018, W221: 2011, W222: 2016, W223: 2021,
    W166: 2016, V167: 2020, X253: 2018, X254: 2023, X156: 2017, H247: 2021, W463: 2019,
    B8: 2014, B9: 2018, C7: 2014, C8: 2019, '8R': 2015, FY: 2019, '4L': 2013, '4M': 2019,
    '6R': 2014, AW: 2020, MK7: 2015, MK8: 2021, B7: 2013, '5N': 2015, AD1: 2020,
    XV50: 2015, XV70: 2019, XA40: 2015, XA50: 2020, '150': 2018, '200': 2018, '300': 2022,
    QB: 2015, FB: 2020, YD: 2016, BD: 2020, QL: 2018, NQ5: 2022, DL3: 2021,
    RB: 2015, HCr: 2020, MD: 2014, AD: 2018, CN7: 2021, TL: 2017, NX4: 2022, DM: 2015, TM: 2019, GS: 2018, SU2: 2022
  };

  function slug(s) {
    return String(s || '')
      .toLowerCase()
      .replace(/ё/g, 'е')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
  }

  function parseCar(value) {
    var v = String(value || '').trim();
    if (!v) return null;
    var brands = Object.keys(MAKE_MAP).concat(Object.keys(MAKE_MAP).map(function () { return null; }));
    // Prefer longest brand match
    var brandList = Object.keys(MAKE_MAP).sort(function (a, b) { return b.length - a.length; });
    for (var i = 0; i < brandList.length; i++) {
      var b = brandList[i];
      if (v === b || v.indexOf(b + ' ') === 0) {
        return { brand: b, model: v.slice(b.length).trim() };
      }
    }
    var parts = v.split(/\s+/);
    return { brand: parts[0], model: parts.slice(1).join(' ') };
  }

  function modelFamily(brand, model) {
    if (!model) return '';
    if (FAMILY_MAP[model]) return FAMILY_MAP[model];
    // BMW "X5" stays x5; "5 Series" handled above
    return slug(model);
  }

  function yearFromHint(hint) {
    if (!hint) return null;
    var code = String(hint).toUpperCase().replace(/[^A-Z0-9]/g, '');
    return CHASSIS_YEAR[code] || null;
  }

  function photoUrl(value, hint, width) {
    var parsed = parseCar(value);
    if (!parsed || !parsed.brand) return '';
    var make = MAKE_MAP[parsed.brand] || slug(parsed.brand);
    var family = modelFamily(parsed.brand, parsed.model) || slug(parsed.brand);
    var year = yearFromHint(hint) || 2020;
    var w = width || 400;
    var params = [
      'customer=img',
      'make=' + encodeURIComponent(make),
      'modelFamily=' + encodeURIComponent(family),
      'modelYear=' + year,
      'angle=23',
      'width=' + w,
      'zoomType=fullscreen'
    ];
    return 'https://cdn.imagin.studio/getImage?' + params.join('&');
  }

  function photoUrlLarge(value, hint) {
    return photoUrl(value, hint, 800);
  }

  global.BS_parseCar = parseCar;
  global.BS_carPhotoUrl = photoUrl;
  global.BS_carPhotoUrlLarge = photoUrlLarge;
})(window);
