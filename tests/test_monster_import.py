import os
import tempfile
import unittest
import zipfile

from src.utils.monster_import import import_monster_images, is_death_frame


class MonsterImportTests(unittest.TestCase):
    def test_death_frame_names_are_recognized(self):
        self.assertTrue(is_death_frame("die1_0.png"))
        self.assertTrue(is_death_frame("monster-death_2.png"))
        self.assertFalse(is_death_frame("move_0.png"))
        self.assertFalse(is_death_frame("hit1_0.png"))

    def test_zip_import_preserves_action_names_and_skips_death_frames(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, "monster.zip")
            target_dir = os.path.join(temp_dir, "target")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("sprites/move_0.png", b"move")
                archive.writestr("sprites/stand_0.png", b"stand")
                archive.writestr("sprites/die1_0.png", b"die")
                archive.writestr("notes.txt", b"ignore")

            result = import_monster_images([archive_path], target_dir)

            self.assertEqual(result.skipped_death_frames, 1)
            self.assertEqual(
                sorted(os.path.basename(path) for path in result.imported_paths),
                ["move_0.png", "stand_0.png"],
            )
            self.assertFalse(os.path.exists(os.path.join(target_dir, "die1_0.png")))


if __name__ == "__main__":
    unittest.main()
