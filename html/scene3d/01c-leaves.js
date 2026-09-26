// Part of the Site & Pattern 3D viewer. Loaded as an ordered CLASSIC
// script by the bootstrap in scene3d.html — it shares the global scope
// with its siblings (THREE and friends are globals set by the
// bootstrap). Do not add ES `import`/`export` here.
//
// Design principle P13 — see docs/DESIGN_PHILOSOPHY.md
//
// How a leaf is lit (F186, V2.94). Seen from a person's height, every crown in
// the viewer read as a black cut-out against the sky, and green from above.
// Two things did it, measured in docs/plans/V2.94-leaves-let-light-through.md:
//
// * A leaf card faces the sky, as a leaf does, so from below a crown is mostly
//   undersides, and an opaque card's underside gets the ground's bounce and no
//   sun. A real leaf seen from below glows: it lets through a good share of the
//   light on its other side. So a leaf takes the sun and the sky falling on its
//   far side too, times the share it lets through (LEAF_TRANSLUCENCY), and a leaf
//   in another's shadow stays in it: the direct light's colour already carries
//   the shadow map.
// * The baked shading (a GLB's grey COLOR_0) multiplied the leaf's colour, so
//   it darkened the sun as well as the sky, and a sunlit leaf inside the crown
//   was shaded twice, once by the shadow map and once by the bake. Occlusion is
//   what the sky cannot reach, so it now dims the sky light, and only a share
//   (BAKE_ON_SUN) of the direct light, the part the 1024-texel shadow map is too
//   coarse to resolve at leaf scale. A tinted colour (the procedural crowns'
//   warm-top gradient) keeps its hue: only its brightness is taken as shade.
//
// Materials opt in through plantMaterial's `translucency`; the surface presets
// take theirs from LEAF_TRANSLUCENCY by key (01b-surface.js surfaceMaterial).

// The share of the light on a leaf's far side that it lets through, per preset.
// Broad leaves the most, needles (thick, and bunched in tufts) the least.
const LEAF_TRANSLUCENCY = { crown: 0.55, shrubLeaf: 0.55, herbLeaf: 0.45, needle: 0.3 };
// How much of the baked shade still falls on the sun (the rest on the sky only).
const BAKE_ON_SUN = 0.3;

function applyLeafLight(shader, T) {
  const t = T.toFixed(3), k = BAKE_ON_SUN.toFixed(3);
  shader.vertexShader = 'varying float vLeafAO;\n' + shader.vertexShader.replace(
    '#include <color_vertex>',
    ['#include <color_vertex>',
     'vLeafAO = 1.0;',
     '#if defined( USE_COLOR ) && ! defined( USE_COLOR_ALPHA )',
     // vColor is color x instanceColor; keep the hue, move the brightness.
     '  vLeafAO = clamp( ( color.r + color.g + color.b ) / 3.0, 0.05, 1.0 );',
     '  vColor.xyz /= vLeafAO;',
     '#endif'].join('\n'));
  shader.fragmentShader = 'varying float vLeafAO;\n' + shader.fragmentShader.replace(
    '#include <lights_physical_pars_fragment>',
    ['#include <lights_physical_pars_fragment>',
     'void RE_Direct_Leaf( const in IncidentLight directLight, const in vec3 geometryPosition,',
     '    const in vec3 geometryNormal, const in vec3 geometryViewDir,',
     '    const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material,',
     '    inout ReflectedLight reflectedLight ) {',
     '  RE_Direct_Physical( directLight, geometryPosition, geometryNormal, geometryViewDir,',
     '                      geometryClearcoatNormal, material, reflectedLight );',
     '  float dotNLb = saturate( dot( - geometryNormal, directLight.direction ) );',
     '  reflectedLight.directDiffuse += ' + t + ' * dotNLb * directLight.color',
     '                                  * BRDF_Lambert( material.diffuseColor );',
     '}',
     '#undef RE_Direct',
     '#define RE_Direct RE_Direct_Leaf'].join('\n'),
  ).replace(
    '#include <lights_fragment_begin>',
    ['#include <lights_fragment_begin>',
     '#if defined( RE_IndirectDiffuse ) && ( NUM_HEMI_LIGHTS > 0 )',
     '  irradiance += ' + t + ' * getHemisphereLightIrradiance( hemisphereLights[ 0 ],',
     '                                                    - geometryNormal );',
     '#endif'].join('\n'),
  ).replace(
    '#include <aomap_fragment>',
    ['#include <aomap_fragment>',
     'reflectedLight.indirectDiffuse *= vLeafAO;',
     'reflectedLight.directDiffuse *= mix( 1.0, vLeafAO, ' + k + ' );'].join('\n'));
}
