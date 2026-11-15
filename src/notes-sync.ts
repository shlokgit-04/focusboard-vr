/**
 * Copyright (c) 2026 Shlok Vane. MIT license.
 *
 * Saves each note's desk spot the moment it is put down, so the board is
 * where you left it next session. Matched to the API by color.
 */
import { createSystem, DistanceGrabbable, Grabbed, Transform } from '@iwsdk/core';
import { fetchBoard, loadConfig, saveNoteSpot, signedIn } from './api.js';

const COLORS = ['amber', 'sage', 'sky', 'rose'] as const;

export class NotesSyncSystem extends createSystem({
  grabbables: { required: [DistanceGrabbable] },
}) {
  private held = new Set<number>();
  private colorToId = new Map<string, string>();
  private queue: Array<{ id: string; x: number; y: number; z: number; ry: number }> = [];
  private pushed = true;

  init(): void {
    void loadConfig().then(() => {
      if (!signedIn()) return;
      fetchBoard()
        .then((notes) => {
          for (const n of notes) {
            if ((COLORS as readonly string[]).includes(n.color)) {
              this.colorToId.set(n.color, n.id);
            }
          }
        })
        .catch(() => {
          /* offline headset: the desk still works, sync retries next launch */
        });
    });
  }

  update(): void {
    if (!this.pushed) {
      this.pushed = true;
      for (const job of this.queue) {
        void saveNoteSpot(job.id, job.x, job.y, job.z, job.ry).catch(() => {
          this.pushed = false;
        });
      }
      this.queue.length = 0;
    }
    for (const entity of this.queries.grabbables.entities) {
      const key = entity.index;
      const isHeld = entity.hasComponent(Grabbed);
      if (isHeld) {
        this.held.add(key);
        continue;
      }
      if (!this.held.delete(key)) continue;
      // Held last frame, free now: the drop moment.
      const sceneName = (entity.object3D?.name || '').toLowerCase();
      const color = COLORS.find((c) => sceneName.includes(c) || sceneName.includes(`note-${c}`));
      if (!color) continue;
      const id = this.colorToId.get(color);
      if (!id) continue; // desk note with no synced counterpart yet
      const pos = entity.getVectorView(Transform, 'position');
      const rot = entity.getVectorView(Transform, 'orientation');
      // yaw from the orientation quaternion (x, y, z, w)
      const yaw = Math.atan2(2 * (rot[3] * rot[1] + rot[0] * rot[2]), 1 - 2 * (rot[1] ** 2 + rot[0] ** 2));
      this.queue.push({
        id,
        x: Math.round(pos[0] * 100) / 100,
        y: Math.round(pos[1] * 100) / 100,
        z: Math.round(pos[2] * 100) / 100,
        ry: Math.round((yaw * 180) / Math.PI),
      });
      this.pushed = false;
    }
  }
}
