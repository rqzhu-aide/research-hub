# Bundled statistical paper skills

These skill resources are copied from `rqzhu-aide/stat-paper-skills` at the
revision recorded in `manifest.json`. Research Hub can install them into a
user-selected Hermes profile, but does not modify profiles during application
installation.

## Tree digest

Each skill digest is SHA-256 over every regular file below that skill's
directory. Convert each relative path to POSIX form, sort the paths
lexicographically, and append the following bytes to one SHA-256 stream for
each file in order:

1. the relative path encoded as UTF-8
2. one NUL byte
3. the raw file contents
4. one NUL byte

Only files within the named skill directory participate in its digest.
Research Hub sidecars at this level, including `manifest.json`, `README.md`,
and the repository-level `LICENSE`, are excluded. The reviewer skill's own
`LICENSE` is inside its directory and is therefore included. The writing
skill's `LICENSE` is a copy of the source repository's root license, placed
inside the installable directory so the notice remains with each profile copy.
