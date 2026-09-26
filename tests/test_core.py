import os
import tempfile
import unittest

from symlink_validator import validate_symlink, SymlinkResult


class TestSymlinkValidator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _join(self, name):
        return os.path.join(self.tmp.name, name)

    def _link(self, src, dst, **kwargs):
        os.symlink(src, dst, **kwargs)

    def test_real_file_target(self):
        target = self._join("target.txt")
        with open(target, "w") as f:
            f.write("hello")
        link = self._join("link.txt")
        self._link(target, link)

        result = validate_symlink(link)
        self.assertTrue(result.exists)
        self.assertFalse(result.circular)
        self.assertFalse(result.depth_exceeded)
        self.assertEqual(result.hops, 1)
        self.assertEqual(result.final_target, os.path.abspath(target))
        self.assertEqual(result.resolved_path, os.path.abspath(target))

    def test_real_dir_target(self):
        target = self._join("target_dir")
        os.mkdir(target)
        link = self._join("link_dir")
        self._link(target, link)

        result = validate_symlink(link)
        self.assertTrue(result.exists)
        self.assertEqual(result.hops, 1)

    def test_broken_symlink(self):
        link = self._join("broken")
        self._link("/nonexistent/target", link)

        result = validate_symlink(link)
        self.assertFalse(result.exists)
        self.assertFalse(result.circular)
        self.assertFalse(result.depth_exceeded)
        self.assertEqual(result.hops, 1)
        self.assertEqual(result.final_target, os.path.normpath("/nonexistent/target"))

    def test_relative_broken_symlink(self):
        link = self._join("rel_broken")
        self._link("does_not_exist", link)

        result = validate_symlink(link)
        self.assertFalse(result.exists)
        self.assertEqual(result.hops, 1)
        expected = os.path.normpath(os.path.join(self.tmp.name, "does_not_exist"))
        self.assertEqual(result.final_target, expected)

    def test_chain_of_symlinks(self):
        final = self._join("final.txt")
        with open(final, "w") as f:
            f.write("x")
        a = self._join("a")
        b = self._join("b")
        c = self._join("c")
        self._link(final, a)
        self._link(a, b)
        self._link(b, c)

        result = validate_symlink(c, max_depth=10)
        self.assertTrue(result.exists)
        self.assertEqual(result.hops, 3)
        self.assertEqual(result.final_target, os.path.abspath(final))

    def test_chain_with_relative_links(self):
        final = self._join("final.txt")
        with open(final, "w") as f:
            f.write("x")
        a = self._join("a")
        b = self._join("b")
        self._link("final.txt", a)
        self._link("a", b)

        result = validate_symlink(b, max_depth=10)
        self.assertTrue(result.exists)
        self.assertEqual(result.hops, 2)
        self.assertEqual(result.final_target, os.path.abspath(final))

    def test_circular_symlink(self):
        a = self._join("a")
        b = self._join("b")
        self._link(b, a)
        self._link(a, b)

        result = validate_symlink(a, max_depth=40)
        self.assertFalse(result.exists)
        self.assertTrue(result.circular)
        self.assertFalse(result.depth_exceeded)
        self.assertGreaterEqual(result.hops, 1)

    def test_self_referential_symlink(self):
        link = self._join("self")
        self._link(link, link)

        result = validate_symlink(link, max_depth=40)
        self.assertFalse(result.exists)
        self.assertTrue(result.circular)

    def test_max_depth_exceeded(self):
        final = self._join("final.txt")
        with open(final, "w") as f:
            f.write("x")
        a = self._join("a")
        b = self._join("b")
        c = self._join("c")
        d = self._join("d")
        self._link(final, a)
        self._link(a, b)
        self._link(b, c)
        self._link(c, d)

        result = validate_symlink(d, max_depth=2)
        self.assertFalse(result.exists)
        self.assertTrue(result.depth_exceeded)
        self.assertEqual(result.hops, 2)

    def test_max_depth_exactly_reached(self):
        final = self._join("final.txt")
        with open(final, "w") as f:
            f.write("x")
        a = self._join("a")
        b = self._join("b")
        self._link(final, a)
        self._link(a, b)

        result = validate_symlink(b, max_depth=2)
        self.assertTrue(result.exists)
        self.assertEqual(result.hops, 2)
        self.assertFalse(result.depth_exceeded)

    def test_max_depth_zero_with_real_target(self):
        final = self._join("final.txt")
        with open(final, "w") as f:
            f.write("x")
        a = self._join("a")
        self._link(final, a)

        result = validate_symlink(a, max_depth=0)
        self.assertFalse(result.exists)
        self.assertTrue(result.depth_exceeded)
        self.assertEqual(result.hops, 0)

    def test_non_symlink_path(self):
        target = self._join("regular.txt")
        with open(target, "w") as f:
            f.write("hi")

        result = validate_symlink(target)
        self.assertTrue(result.exists)
        self.assertEqual(result.hops, 0)
        self.assertFalse(result.circular)
        self.assertFalse(result.depth_exceeded)
        self.assertEqual(result.final_target, os.path.abspath(target))

    def test_non_existent_non_symlink(self):
        missing = self._join("missing.txt")
        result = validate_symlink(missing)
        self.assertFalse(result.exists)
        self.assertEqual(result.hops, 0)
        self.assertFalse(result.circular)
        self.assertFalse(result.depth_exceeded)

    def test_negative_max_depth_rejected(self):
        with self.assertRaises(ValueError):
            validate_symlink("/tmp", max_depth=-1)

    def test_symlink_to_non_symlink_relative(self):
        final = self._join("final.txt")
        with open(final, "w") as f:
            f.write("x")
        a = self._join("a")
        self._link("final.txt", a)

        result = validate_symlink(a)
        self.assertTrue(result.exists)
        self.assertEqual(result.hops, 1)
        self.assertEqual(result.final_target, os.path.abspath(final))

    def test_long_chain_just_within_depth(self):
        final = self._join("final.txt")
        with open(final, "w") as f:
            f.write("x")
        links = []
        for i in range(5):
            ln = self._join(f"l{i}")
            if i == 0:
                self._link(final, ln)
            else:
                self._link(links[i - 1], ln)
            links.append(ln)

        result = validate_symlink(links[-1], max_depth=5)
        self.assertTrue(result.exists)
        self.assertEqual(result.hops, 5)
        self.assertFalse(result.depth_exceeded)

    def test_result_is_dataclass_instance(self):
        target = self._join("t.txt")
        with open(target, "w") as f:
            f.write("x")
        link = self._join("ln")
        self._link(target, link)

        result = validate_symlink(link)
        self.assertIsInstance(result, SymlinkResult)
        # All fields accessible
        for field in ("exists", "final_target", "circular", "depth_exceeded", "hops", "resolved_path"):
            self.assertTrue(hasattr(result, field))


if __name__ == "__main__":
    unittest.main()
