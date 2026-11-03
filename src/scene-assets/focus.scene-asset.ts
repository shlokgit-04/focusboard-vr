/**
 * Copyright (c) 2026 Shlok Vane. MIT license.
 *
 * FocusBoard VR scene assets: thin sticky-note tiles you pinch and arrange,
 * built with procedural primitives so the build downloads no extra models.
 */
import {
  createSceneMaterial,
  createScenePrimitiveObject,
  Mesh,
} from '@iwsdk/core';

function stickyTile(color: `#${string}`, width = 0.17): Mesh {
  const material = createSceneMaterial({
    id: `note-${color.replace('#', '')}`,
    model: 'standard',
    baseColor: color,
    roughness: 0.62,
  });
  return createScenePrimitiveObject(
    {
      geometry: {
        type: 'roundedBox',
        size: [width, 0.022, width],
        radius: 0.006,
        segments: 3,
      },
    },
    material,
  );
}

export const createNoteAmber = (): Mesh => stickyTile('#F7D154');
export const createNoteSage = (): Mesh => stickyTile('#9FD8AE');
export const createNoteSky = (): Mesh => stickyTile('#9CC3F5');
export const createNoteRose = (): Mesh => stickyTile('#F5A8A8');

/** A low wooden tray the notes rest on between sessions. */
export function createNoteTray(): Mesh {
  const wood = createSceneMaterial({
    id: 'note-tray-wood',
    model: 'standard',
    baseColor: '#D9C7A7',
    roughness: 0.8,
  });
  return createScenePrimitiveObject(
    {
      geometry: {
        type: 'roundedBox',
        size: [0.62, 0.02, 0.46],
        radius: 0.02,
        segments: 3,
      },
    },
    wood,
  );
}
