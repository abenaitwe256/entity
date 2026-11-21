# Hologram (Pepper's Ghost) Notes

This prototype includes a **Pepper's Ghost hologram mode**: the renderer draws four rotated views of the scene into screen quadrants. When a clear acrylic pyramid is placed on the screen, reflections create a floating 3D illusion.

## Usage

1. Run the app and switch to **Hologram** mode.
2. Place a Pepper's Ghost pyramid centered on the screen.
3. View from the side of the pyramid (lighting conditions matter).

## Calibration considerations

- Pyramid size/angles must match the quadrant layout and screen size.
- Brightness, contrast, and ambient light strongly affect perceived quality.
- A black background improves reflection contrast (the renderer clears to transparent/black per view area).
- Future work: on-screen calibration guides, per-device presets, and alignment offsets.

## Hardware

- Phone/tablet screen as the image source.
- DIY pyramid: clear acrylic/PETG sheet cut into trapezoids (many open templates exist online). Add printable templates and dimensions here as they are validated.

## Relation to optical see-through glasses

Pepper's Ghost is a simple, accessible holographic presentation. The same scene/interaction stack can target other device-mediated views (phone AR, HoloKit-style phone+optics, or future open optical see-through glasses) while preserving the "virtual content visible only through a device" constraint.
