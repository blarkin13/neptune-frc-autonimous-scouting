"""Tests for wide-shot robot tracking: colour masks, static background, field band, blobs, linking,
identity votes, hub lines, alliance-relative positions and track-guided crops."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import neptune_tracking as nt


def planes(pixels):
    """[(Y, U, V)] -> three plane byte strings."""
    return tuple(bytes(p[i] for p in pixels) for i in range(3))


def mask(width, height, on):
    """Big-integer mask with 0xFF at the (x, y) pixels in `on`."""
    data = bytearray(width * height)
    for x, y in on:
        data[y * width + x] = 255
    return int.from_bytes(bytes(data), 'big')


RED_PX, BLUE_PX, FUEL_PX, GREY_PX = (80, 122, 170), (90, 160, 115), (190, 40, 142), (60, 128, 129)


def det(cx, cy, colour='red', w=10, h=4, n=30):
    x0, y0 = int(cx - w / 2), int(cy - h + 1)
    return {'x0': x0, 'x1': x0 + w - 1, 'y0': y0, 'y1': int(cy), 'n': n, 'cx': cx, 'cy': cy, 'colour': colour}


def read(team, t, box, kind='exact', background=None):
    return {'team': team, 't': t, 'kind': kind, 'background': background, 'frame_box': box, 'text': str(team), 'frame': 'f.jpg'}


ROSTER = {'red': [111, 222, 333], 'blue': [444, 555, 666]}


class ColourTests(unittest.TestCase):
    def test_classify_separates_bumpers_fuel_and_floor(self):
        y, u, v = planes([RED_PX, BLUE_PX, FUEL_PX, GREY_PX])
        red, blue, yellow = (m.to_bytes(4, 'big') for m in nt.classify(y, u, v))
        self.assertEqual(red, b'\xff\x00\x00\x00')
        self.assertEqual(blue, b'\x00\xff\x00\x00')
        self.assertEqual(yellow, b'\x00\x00\xff\x00')

    def test_skin_and_wood_are_not_fuel(self):
        y, u, v = planes([(150, 112, 145), (120, 114, 138)])
        self.assertEqual(nt.classify(y, u, v)[2], 0)


class BackgroundTests(unittest.TestCase):
    def test_static_colour_is_removed_and_counts_survive_many_frames(self):
        # pixel 0 red in every frame (a hub ramp); pixel 1 red in 10% (a passing robot); 300 frames > 255.
        bg = nt.Background(3)
        for k in range(300):
            red = mask(3, 1, [(0, 0)] + ([(1, 0)] if k % 10 == 0 else []))
            bg.add((red, 0, mask(3, 1, [(2, 0)] if k % 2 else [])))
        keep_red, keep_blue, yellow = bg.masks()
        self.assertEqual(keep_red.to_bytes(3, 'big'), b'\x00\xff\xff')
        self.assertEqual(keep_blue.to_bytes(3, 'big'), b'\xff\xff\xff')
        self.assertEqual(bg.counts[nt.RED][1], 30)
        self.assertAlmostEqual(yellow[2], 0.5)

    def test_field_band_skips_audience_and_static_banner(self):
        width, height = 50, 40
        share = [0.0] * (width * height)
        for row in range(height):
            for x in range(width):
                if 3 <= row < 9 and x % 3 == 0:
                    share[row * width + x] = 0.05     # audience: short band
                if row >= 14 and 5 <= x < 45 and row != 30:
                    share[row * width + x] = 0.2      # fuel on the floor, one empty row
                if row < 12 and x < 5:
                    share[row * width + x] = 0.9      # static yellow banner
        rows = nt.field_rows(share, width, height)
        self.assertIsNone(rows[5])
        self.assertTrue(all(rows[r] for r in range(16, height)))
        self.assertLessEqual(rows[20][0], 5)
        self.assertGreaterEqual(rows[20][1], 44)

    def test_field_band_survives_a_four_row_gap(self):
        # regression: a band ending in a gap of exactly 4 rows was dropped, leaving no field at all
        width, height = 30, 60
        share = [0.0] * (width * height)
        for row in list(range(20, 40)) + list(range(44, 60)):
            for x in range(width):
                share[row * width + x] = 0.2
        rows = nt.field_rows(share, width, height)
        self.assertTrue(rows[25] and rows[50])


class BlobTests(unittest.TestCase):
    def test_runs_bridge_digits_and_rows_join(self):
        width, height = 30, 6
        on = [(x, 2) for x in range(5, 20) if x not in (10, 11)] + [(x, 3) for x in range(5, 20)] + [(26, 5)]
        data = mask(width, height, on).to_bytes(width * height, 'big')
        found = nt.blobs(data, width, height)
        self.assertEqual(len(found), 1)
        b = found[0]
        self.assertEqual((b['x0'], b['x1'], b['y0'], b['y1']), (5, 19, 2, 3))
        self.assertEqual(b['n'], 28)
        self.assertTrue(nt.bumper_like(b))

    def test_bumper_halves_split_by_the_number_are_joined(self):
        left = {'x0': 10, 'x1': 19, 'y0': 50, 'y1': 54, 'n': 50, 'cx': 14.5, 'cy': 54, 'colour': 'blue'}
        right = {'x0': 30, 'x1': 39, 'y0': 51, 'y1': 55, 'n': 50, 'cx': 34.5, 'cy': 55, 'colour': 'blue'}
        other = {'x0': 42, 'x1': 50, 'y0': 50, 'y1': 54, 'n': 45, 'cx': 46, 'cy': 54, 'colour': 'red'}
        far = {'x0': 80, 'x1': 90, 'y0': 50, 'y1': 54, 'n': 55, 'cx': 85, 'cy': 54, 'colour': 'blue'}
        out = nt.merge_split([right, other, left, far])
        self.assertEqual(sorted((b['colour'], b['x0'], b['x1']) for b in out), [('blue', 10, 39), ('blue', 80, 90), ('red', 42, 50)])
        self.assertEqual(next(b for b in out if b['x0'] == 10)['cy'], 55)

    def test_tall_shapes_are_not_bumpers(self):
        self.assertFalse(nt.bumper_like({'x0': 0, 'x1': 5, 'y0': 0, 'y1': 19, 'n': 120}))


class LinkTests(unittest.TestCase):
    def test_two_robots_with_a_dropout_stay_two_tracks(self):
        frames = []
        for k in range(30):
            t = k / 3
            dets = [det(50 + 6 * t, 80, 'red'), det(300 - 6 * t, 120, 'red')]
            if k in (10, 11):
                dets = dets[1:]          # first robot hidden for two frames
            frames.append((round(t, 3), dets))
        tracks = nt.link(frames, 3.0)
        self.assertEqual(len(tracks), 2)
        self.assertEqual(sorted(len(tr['points']) for tr in tracks), [28, 30])

    def test_far_jump_starts_a_new_track(self):
        frames = [(k / 3, [det(100, 100)]) for k in range(5)] + [(5 / 3 + k / 3, [det(400, 100)]) for k in range(5)]
        self.assertEqual(len(nt.link(frames, 3.0)), 2)


class IdentityTests(unittest.TestCase):
    band, camera_top, width, height = (0.12, 0.64), 0.12, 640, 200

    def box_at(self, cx, cy):
        """frame_box (camera-area fractions) whose centre lands on work pixel (cx, cy)."""
        top, bottom = self.band
        fy = top + cy / self.height * (bottom - top)
        y = (fy - self.camera_top) / (1 - self.camera_top)
        return [cx / self.width - 0.01, y - 0.005, 0.02, 0.01]

    def tracks(self):
        frames = [(round(k / 3, 3), [det(100 + k, 100, 'red'), det(400, 150, 'red'), det(250, 60, 'blue')]) for k in range(30)]
        return nt.link(frames, 3.0)

    def test_reads_vote_for_the_track_under_them(self):
        tracks = self.tracks()
        reads = [read(111, 2.0, self.box_at(105, 99)), read(111, 2.0, self.box_at(105, 99)),   # one frame, two tiles
                 read(111, 4.0, self.box_at(111, 99)),
                 read(222, 4.0, self.box_at(400, 149)), read(222, 6.0, self.box_at(400, 149)),
                 read(444, 6.0, self.box_at(250, 59)), read(444, 8.0, self.box_at(250, 59), kind='corrected'),
                 read(444, 9.0, self.box_at(250, 59), kind='corrected'),
                 read(333, 4.0, self.box_at(250, 59)), read(333, 5.0, self.box_at(250, 59)),     # red team on a blue robot
                 read(555, 8.0, self.box_at(400, 149), background='red'),                          # wrong colour, rejected
                 read(555, 9.0, self.box_at(400, 149), background='red')]
        assigned, votes = nt.assign_identities(tracks, reads, ROSTER, self.band, self.camera_top, self.width, self.height)
        teams = {tr['colour'] + str(round(tr['points'][0][1])): assigned.get(tr['id'], {}).get('team') for tr in tracks}
        self.assertEqual(teams, {'red100': 111, 'red400': 222, 'blue250': None})
        first = next(tr for tr in tracks if tr['points'][0][1] == 100)
        self.assertEqual(votes[first['id']][111], 2.0)

    def test_one_moment_is_not_enough(self):
        tracks = self.tracks()
        reads = [read(111, 2.0, self.box_at(105, 99)), read(111, 2.0, self.box_at(105, 99))]
        p = next(tr for tr in tracks if tr['points'][0][1] == 100)['points'][6]
        own = [{'team': 111, 't': 2.0, 'at': p[0], 'box': list(p[3:7]), 'kind': 'exact', 'text': '111'}]   # same moment
        assigned, votes = nt.assign_identities(tracks, reads, ROSTER, self.band, self.camera_top, self.width, self.height, own_reads=own)
        self.assertEqual(assigned, {})

    def test_read_beside_a_bumper_does_not_vote(self):
        tracks = self.tracks()
        reads = [read(111, t, self.box_at(100 + 3 * t + 20, 99)) for t in (2.0, 4.0, 6.0)]   # 20 px right of the strip
        assigned, _ = nt.assign_identities(tracks, reads, ROSTER, self.band, self.camera_top, self.width, self.height)
        self.assertEqual(assigned, {})

    def test_team_never_holds_two_overlapping_tracks(self):
        tracks = self.tracks()
        reads = [read(111, t, self.box_at(100 + 3 * t + 3, 99)) for t in (2.0, 4.0, 6.0)] + [read(111, 2.0, self.box_at(400, 149))]
        assigned, _ = nt.assign_identities(tracks, reads, ROSTER, self.band, self.camera_top, self.width, self.height)
        self.assertEqual(sorted(a['team'] for a in assigned.values()), [111])

    def test_track_guided_reads_follow_their_detection(self):
        tracks = self.tracks()
        p = next(tr for tr in tracks if tr['points'][0][1] == 400)['points'][6]
        q = next(tr for tr in tracks if tr['points'][0][1] == 400)['points'][9]
        own = [{'team': 333, 't': 2.0, 'at': p[0], 'box': list(p[3:7]), 'kind': 'exact', 'text': '333'},
               {'team': 333, 't': 3.0, 'at': q[0], 'box': list(q[3:7]), 'kind': 'exact', 'text': '333'},
               {'team': 444, 't': 2.0, 'at': p[0], 'box': list(p[3:7]), 'kind': 'exact', 'text': '444'},   # blue team on red robot
               {'team': 444, 't': 3.0, 'at': q[0], 'box': list(q[3:7]), 'kind': 'exact', 'text': '444'}]
        assigned, _ = nt.assign_identities(tracks, [], ROSTER, self.band, self.camera_top, self.width, self.height, own_reads=own)
        self.assertEqual([a['team'] for a in assigned.values()], [333])

    def test_unread_continuation_inherits_identity(self):
        frames = [(round(k / 3, 3), [det(100 + 2 * k, 100)]) for k in range(10)]
        frames += [(round((k + 12) / 3, 3), [det(100 + 2 * (k + 12), 100)]) for k in range(10)]   # 1 s gap
        tracks = nt.link(frames, 3.0, max_gap_s=0.5)
        self.assertEqual(len(tracks), 2)
        voted = {tracks[0]['id']: {'team': 111, 'votes': 3, 'other_votes': 0}}
        out = nt.extend_identities(tracks, voted)
        self.assertEqual(out[tracks[1]['id']]['team'], 111)
        self.assertEqual(out[tracks[1]['id']]['inherited'], tracks[0]['id'])

    def test_bridge_and_coverage(self):
        pts = [(0.0, 10, 10), (0.33, 11, 10), (2.0, 20, 10), (9.0, 100, 10)]
        filled = nt.bridge(pts, max_gap=3.0)
        self.assertTrue(any(not p[3] and 0.33 < p[0] < 2.0 for p in filled))
        self.assertFalse(any(not p[3] and p[0] > 2.0 for p in filled))   # 7 s gap stays open
        cov = nt.coverage({1: filled, 2: []}, 0.0, 9.0)
        self.assertAlmostEqual(cov[1], 4 / 10)
        self.assertEqual(cov[2], 0.0)


class GeometryTests(unittest.TestCase):
    def test_hub_line_follows_the_ramp_not_a_post(self):
        width, height = 200, 60
        rows = [None] * 10 + [(0, 199)] * 50
        static = [(int(60 - 0.5 * r) + dx, r) for r in range(10, 60) for dx in range(-6, 7)]   # slanted hub/ramp strip
        static += [(180, r) for r in range(10, 60)] + [(181, r) for r in range(10, 60)] + [(182, r) for r in range(10, 60)] + [(183, r) for r in range(10, 60)]
        keep = ~mask(width, height, static) & ((1 << (8 * width * height)) - 1)
        line = nt.hub_line(keep, rows, width)
        self.assertAlmostEqual(line['b'], -0.5, delta=0.05)
        self.assertAlmostEqual(nt.hub_x(line, 40), 40, delta=2)

    def test_alliance_relative_zones(self):
        hubs = {'blue': {'a': 100.0, 'b': -0.5}, 'red': {'a': 500.0, 'b': 0.5}}   # blue hub on the left
        self.assertEqual(nt.own_side(hubs), {'blue': -1, 'red': 1})
        at = lambda x, al: nt.position(x, 100, al, hubs)
        self.assertEqual(at(20, 'blue')['zone'], 'own')
        self.assertEqual(at(300, 'blue')['zone'], 'neutral')
        self.assertEqual(at(600, 'blue')['zone'], 'opponent')
        self.assertEqual(at(600, 'red')['zone'], 'own')
        self.assertAlmostEqual(at(50, 'blue')['u'], 0.0)                         # on the blue hub line at row 100
        self.assertAlmostEqual(at(300, 'red')['hub_m'], nt.HUB_SPACING_M / 2, places=2)


class CropTests(unittest.TestCase):
    def test_bmp_is_bottom_up_and_padded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.bmp'
            nt.write_bmp(path, 3, 2, [b'\x01\x02\x03' * 3, b'\x04\x05\x06' * 3])
            data = path.read_bytes()
            self.assertEqual(data[:2], b'BM')
            self.assertEqual(len(data), 54 + 2 * 12)
            self.assertEqual(data[54:63], b'\x04\x05\x06' * 3)   # last row first

    def test_crop_box_stays_inside_the_band(self):
        x, y, w, h = nt.crop_box((0.0, 5, 3, 0, 1, 10, 3, 20), 640, 3840, 1160)
        self.assertEqual((x, y), (0, 0))
        self.assertTrue(w > 0 and h > 0 and x + w <= 3840 and y + h <= 1160)

    def test_read_targets_one_per_second(self):
        tr = {'id': 7, 'points': [(round(k / 3, 3), 0, 0, 0, 0, 1, 1, 9) for k in range(10)]}
        self.assertEqual(sorted(nt.read_targets([tr], 0.0)), [0, 1, 2, 3])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg missing')
class EndToEndTests(unittest.TestCase):
    def test_moving_bumpers_tracked_and_static_ramp_ignored(self):
        # 640x360 "broadcast": overlay band on top, wide shot below. A static red ramp, flickering fuel that
        # marks the floor, a red robot driving right and a blue robot driving left.
        fuel = ','.join("drawbox=x=%d:y=%d:w=8:h=8:color=yellow:t=fill:enable='lt(mod(t+%g,4),2)'" % (20 + 40 * (i % 15), 130 + 12 * (i // 15), i * 0.3)
                         for i in range(15 * 18))
        scene = ("[0]drawbox=x=0:y=0:w=640:h=60:color=black:t=fill,drawbox=x=0:y=110:w=640:h=250:color=0x505052:t=fill,%s,"
                 "drawbox=x=300:y=180:w=40:h=60:color=0xc82828:t=fill[field];"
                 "color=0xc82828:s=48x12:r=15[r];color=0x2040e0:s=48x12:r=15[b];"
                 "[field][r]overlay=x='40+40*t':y=250:shortest=1[a];[a][b]overlay=x='560-40*t':y=270:shortest=1") % fuel
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / 'v.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=0x303030:s=640x360:r=15:d=10', '-filter_complex', scene,
                            '-pix_fmt', 'yuv420p', str(video)], check=True)
            profile = {'camera_top': 0.12, 'closeup_top': 1.0}
            out = nt.detect(video, profile, 0.0, 10.0, fps=3.0, width=320)
            self.assertTrue(any(out['field']))
            tracks = [tr for tr in nt.link(out['frames'], out['fps']) if len(tr['points']) >= 15]
            self.assertEqual(sorted(tr['colour'] for tr in tracks), ['blue', 'red'])
            red = next(tr for tr in tracks if tr['colour'] == 'red')
            self.assertGreater(red['points'][-1][1] - red['points'][0][1], 100)   # it moved right
            self.assertIsNotNone(out['hubs']['red'])
            self.assertAlmostEqual(nt.hub_x(out['hubs']['red'], 100), 160, delta=12)   # the static ramp, in work pixels


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class RawFrameGeometryTests(unittest.TestCase):
    def test_fractional_camera_crops_keep_complete_frames_and_yuv_planes(self):
        # These geometries made scale=-2 emit a different height than the raw
        # reader expected. Constant red must remain constant in every plane.
        cases=[(1280,720,.6656,1.,0.,.5),
               (1280,720,.67,1.,0.,.5),
               (1920,1080,.12,.655,0.,1.),
               (854,480,.24,.6506,0.,1.)]
        with tempfile.TemporaryDirectory() as temp:
            for sw,sh,top,bottom,left,right in cases:
                with self.subTest(source=(sw,sh),crop=(top,bottom,left,right)):
                    video=Path(temp)/'red.mkv'
                    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i',
                                    'color=red:s=%dx%d:r=6'%(sw,sh),'-t','1','-c:v','ffv1',str(video)],check=True)
                    frames=list(nt.decode(video,top,bottom,0,1,6,960,left,right))
                    self.assertEqual(len(frames),6)
                    for t,w,h,y,u,v in frames:
                        self.assertEqual(len(y),w*h)
                        self.assertTrue(all(max(p)-min(p)<=1 for p in (y,u,v)))
                        self.assertLess(abs(y[0]-81),3)
                        self.assertLess(abs(u[0]-90),3)
                        self.assertLess(abs(v[0]-240),3)


if __name__ == '__main__':
    unittest.main()
