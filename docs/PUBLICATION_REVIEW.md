# Publication and independent privacy review

This public repository contains a generic SMF analysis tool. Project-owned
examples must use newly invented names, measurement values, times and
topologies. Published IBM examples may be used with their primary-source
attribution. Neither kind of example represents a site's actual inventory.

## Before publication

1. Review source, tests, examples, JCL and documents for actual site names,
   dataset/logstream names, machine or partition identifiers, addresses,
   credentials and real measurement traces. Examine literal values and
   images as well as obvious file extensions. A generic filename does
   not establish that its contents are fictional.
2. Confirm that fixtures were independently invented for a stated test.
   Renaming a system or transforming values from an actual trace does
   not make that trace suitable for this public repository. Keep actual
   host and SCRT comparison evidence in an approved private location.
3. Inspect Git author/committer names and email addresses before creating
   commits, using an owner-approved public attribution identity. Review
   commit messages, branch names and PR descriptions for private context.
   Owner-approved name and email attribution may remain public; the check
   is for unintended disclosure, not a ban on public author credit.
4. Review the proposed final tree and all reachable history in scope,
   including deleted files. State which refs were included and whether
   the checkout contains full history. A current-tree scan alone cannot
   establish that earlier material was removed.
5. Inspect GitHub surfaces outside tracked files separately: PR and issue
   text, attachments, CI output/artifacts, releases and any other relevant
   publication surfaces. Do not imply these were checked when they were not.
6. Run the relevant regressions and document-link/JCL format checks after
   replacing examples. Check that the newly invented arithmetic and its
   expected results agree across documentation and test fixtures.

Useful local inspection commands include:

```text
git status --short
git diff --check
git log --all --format='%H %an <%ae> %cn <%ce>'
git log --all --format= --name-status
git rev-list --objects --all
```

These commands are inspection aids, not a complete automated secret scanner.
Review their output privately; do not paste private findings into public
logs or describe removed values in a public cleanup commit message.

## Independent repeat review

After cleanup, a reviewer who did not perform the edits should repeat the
inspection against the exact proposed publication commit. Record the refs
and surfaces checked, the checks run, outstanding findings and the limits
of the conclusion. Confirm that fictional fixture labels are accurate and
that no real identifiers were reintroduced while updating examples.

A successful review is bounded evidence about the inspected material. It
cannot guarantee the absence of unknown site identifiers without a verified
inventory, nor establish that external copies no longer exist.

## Current files and historical copies

Cleaning the latest tree does not erase old commits, previous PR diffs,
existing clones, forks or cached copies. If historical cleanup is needed,
prepare a separate owner-authorized plan covering affected refs, collaborator
coordination and verification. Do not claim that a normal follow-up commit
removes earlier material. Private evidence and removed values must stay out
of the public audit trail throughout that work.
