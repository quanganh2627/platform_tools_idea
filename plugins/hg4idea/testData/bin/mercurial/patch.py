import cStringIO, email.Parser, os, errno, re, posixpath
import tempfile, zlib, shutil

import base85, mdiff, scmutil, util, diffhelpers, copies, encoding, error
import context
    if not util.safehasattr(stream, 'next'):
    return tuple (filename, message, user, date, branch, node, p1, p2).
            subject = re.sub(r'\n[ \t]+', ' ', subject)
                hgpatchheader = False
                    if line.startswith('# HG changeset patch') and not hgpatch:
                        hgpatchheader = True
                    elif hgpatchheader:
                            parents.append(line[9:].lstrip())
                        elif not line.startswith("# "):
                            hgpatchheader = False
                    if not hgpatchheader and not ignoretext:
    except: # re-raises
    def copy(self):
        other = patchmeta(self.path)
        other.oldpath = self.oldpath
        other.mode = self.mode
        other.op = self.op
        other.binary = self.binary
        return other

    def _ispatchinga(self, afile):
        if afile == '/dev/null':
            return self.op == 'ADD'
        return afile == 'a/' + (self.oldpath or self.path)

    def _ispatchingb(self, bfile):
        if bfile == '/dev/null':
            return self.op == 'DELETE'
        return bfile == 'b/' + self.path

    def ispatching(self, afile, bfile):
        return self._ispatchinga(afile) and self._ispatchingb(bfile)

    def __repr__(self):
        return "<patchmeta %s %r>" % (self.op, self.path)

        if line.startswith('diff --git a/'):
    return gitpatches
    def __init__(self, fp):
        return self.fp.readline()
        while True:
class abstractbackend(object):
    def __init__(self, ui):
        self.ui = ui

    def getfile(self, fname):
        """Return target file data and flags as a (data, (islink,
        isexec)) tuple.
        """
        raise NotImplementedError

    def setfile(self, fname, data, mode, copysource):
        """Write data to target file fname and set its mode. mode is a
        (islink, isexec) tuple. If data is None, the file content should
        be left unchanged. If the file is modified after being copied,
        copysource is set to the original file name.
        """
        raise NotImplementedError

    def unlink(self, fname):
        """Unlink target file."""
        raise NotImplementedError

    def writerej(self, fname, failed, total, lines):
        """Write rejected lines for fname. total is the number of hunks
        which failed to apply and total the total number of hunks for this
        files.
        """
        pass

    def exists(self, fname):
        raise NotImplementedError

class fsbackend(abstractbackend):
    def __init__(self, ui, basedir):
        super(fsbackend, self).__init__(ui)
        self.opener = scmutil.opener(basedir)

    def _join(self, f):
        return os.path.join(self.opener.base, f)

    def getfile(self, fname):
        path = self._join(fname)
        if os.path.islink(path):
            return (os.readlink(path), (True, False))
        isexec = False
        try:
            isexec = os.lstat(path).st_mode & 0100 != 0
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
        return (self.opener.read(fname), (False, isexec))

    def setfile(self, fname, data, mode, copysource):
        islink, isexec = mode
        if data is None:
            util.setflags(self._join(fname), islink, isexec)
            return
        if islink:
            self.opener.symlink(data, fname)
        else:
            self.opener.write(fname, data)
            if isexec:
                util.setflags(self._join(fname), False, True)

    def unlink(self, fname):
        util.unlinkpath(self._join(fname), ignoremissing=True)

    def writerej(self, fname, failed, total, lines):
        fname = fname + ".rej"
        self.ui.warn(
            _("%d out of %d hunks FAILED -- saving rejects to file %s\n") %
            (failed, total, fname))
        fp = self.opener(fname, 'w')
        fp.writelines(lines)
        fp.close()

    def exists(self, fname):
        return os.path.lexists(self._join(fname))

class workingbackend(fsbackend):
    def __init__(self, ui, repo, similarity):
        super(workingbackend, self).__init__(ui, repo.root)
        self.repo = repo
        self.similarity = similarity
        self.removed = set()
        self.changed = set()
        self.copied = []

    def _checkknown(self, fname):
        if self.repo.dirstate[fname] == '?' and self.exists(fname):
            raise PatchError(_('cannot patch %s: file is not tracked') % fname)

    def setfile(self, fname, data, mode, copysource):
        self._checkknown(fname)
        super(workingbackend, self).setfile(fname, data, mode, copysource)
        if copysource is not None:
            self.copied.append((copysource, fname))
        self.changed.add(fname)

    def unlink(self, fname):
        self._checkknown(fname)
        super(workingbackend, self).unlink(fname)
        self.removed.add(fname)
        self.changed.add(fname)

    def close(self):
        wctx = self.repo[None]
        addremoved = set(self.changed)
        for src, dst in self.copied:
            scmutil.dirstatecopy(self.ui, self.repo, wctx, src, dst)
        if self.removed:
            wctx.forget(sorted(self.removed))
            for f in self.removed:
                if f not in self.repo.dirstate:
                    # File was deleted and no longer belongs to the
                    # dirstate, it was probably marked added then
                    # deleted, and should not be considered by
                    # addremove().
                    addremoved.discard(f)
        if addremoved:
            cwd = self.repo.getcwd()
            if cwd:
                addremoved = [util.pathto(self.repo.root, cwd, f)
                              for f in addremoved]
            scmutil.addremove(self.repo, addremoved, similarity=self.similarity)
        return sorted(self.changed)

class filestore(object):
    def __init__(self, maxsize=None):
        self.opener = None
        self.files = {}
        self.created = 0
        self.maxsize = maxsize
        if self.maxsize is None:
            self.maxsize = 4*(2**20)
        self.size = 0
        self.data = {}

    def setfile(self, fname, data, mode, copied=None):
        if self.maxsize < 0 or (len(data) + self.size) <= self.maxsize:
            self.data[fname] = (data, mode, copied)
            self.size += len(data)
        else:
            if self.opener is None:
                root = tempfile.mkdtemp(prefix='hg-patch-')
                self.opener = scmutil.opener(root)
            # Avoid filename issues with these simple names
            fn = str(self.created)
            self.opener.write(fn, data)
            self.created += 1
            self.files[fname] = (fn, mode, copied)

    def getfile(self, fname):
        if fname in self.data:
            return self.data[fname]
        if not self.opener or fname not in self.files:
            raise IOError
        fn, mode, copied = self.files[fname]
        return self.opener.read(fn), mode, copied

    def close(self):
        if self.opener:
            shutil.rmtree(self.opener.base)

class repobackend(abstractbackend):
    def __init__(self, ui, repo, ctx, store):
        super(repobackend, self).__init__(ui)
        self.repo = repo
        self.ctx = ctx
        self.store = store
        self.changed = set()
        self.removed = set()
        self.copied = {}

    def _checkknown(self, fname):
        if fname not in self.ctx:
            raise PatchError(_('cannot patch %s: file is not tracked') % fname)

    def getfile(self, fname):
        try:
            fctx = self.ctx[fname]
        except error.LookupError:
            raise IOError
        flags = fctx.flags()
        return fctx.data(), ('l' in flags, 'x' in flags)

    def setfile(self, fname, data, mode, copysource):
        if copysource:
            self._checkknown(copysource)
        if data is None:
            data = self.ctx[fname].data()
        self.store.setfile(fname, data, mode, copysource)
        self.changed.add(fname)
        if copysource:
            self.copied[fname] = copysource

    def unlink(self, fname):
        self._checkknown(fname)
        self.removed.add(fname)

    def exists(self, fname):
        return fname in self.ctx

    def close(self):
        return self.changed | self.removed

unidesc = re.compile('@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
contextdesc = re.compile('(?:---|\*\*\*) (\d+)(?:,(\d+))? (?:---|\*\*\*)')
    def __init__(self, ui, gp, backend, store, eolmode='strict'):
        self.fname = gp.path
        self.backend = backend
        self.missing = True
        self.mode = gp.mode
        self.copysource = gp.oldpath
        self.create = gp.op in ('ADD', 'COPY', 'RENAME')
        self.remove = gp.op == 'DELETE'
        try:
            if self.copysource is None:
                data, mode = backend.getfile(self.fname)
            else:
                data, mode = store.getfile(self.copysource)[:2]
                self.exists = backend.exists(self.fname)
            self.missing = False
            if data:
                self.lines = mdiff.splitnewlines(data)
            if self.mode is None:
                self.mode = mode
            if self.lines:
                # Normalize line endings
                if self.lines[0].endswith('\r\n'):
                    self.eol = '\r\n'
                elif self.lines[0].endswith('\n'):
                    self.eol = '\n'
                if eolmode != 'strict':
                    nlines = []
                    for l in self.lines:
                        if l.endswith('\r\n'):
                            l = l[:-2] + '\n'
                        nlines.append(l)
                    self.lines = nlines
        except IOError:
            if self.create:
                self.missing = False
            if self.mode is None:
                self.mode = (False, False)
        if self.missing:
    def writelines(self, fname, lines, mode):
        if self.eolmode == 'auto':
            eol = self.eol
        elif self.eolmode == 'crlf':
            eol = '\r\n'
            eol = '\n'
        if self.eolmode != 'strict' and eol and eol != '\n':
            rawlines = []
            for l in lines:
                if l and l[-1] == '\n':
                    l = l[:-1] + eol
                rawlines.append(l)
            lines = rawlines
        self.backend.setfile(fname, ''.join(lines), mode, self.copysource)
        base = os.path.basename(self.fname)
        lines = ["--- %s\n+++ %s\n" % (base, base)]
        for x in self.rej:
            for l in x.hunk:
                lines.append(l)
                if l[-1] != '\n':
                    lines.append("\n\ No newline at end of file\n")
        self.backend.writerej(self.fname, len(self.rej), self.hunks, lines)
        if self.exists and self.create:
            if self.copysource:
                self.ui.warn(_("cannot create %s: destination already "
                               "exists\n" % self.fname))
            else:
                self.ui.warn(_("file %s already exists\n") % self.fname)
            if self.remove:
                self.backend.unlink(self.fname)
                self.dirty = True
        old, oldstart, new, newstart = h.fuzzit(0, False)
        oldstart += self.offset
        orig_start = oldstart
        if (self.skew == 0 and
            diffhelpers.testhunk(old, self.lines, oldstart) == 0):
            if self.remove:
                self.backend.unlink(self.fname)
                self.lines[oldstart:oldstart + len(old)] = new
                self.offset += len(new) - len(old)
                self.dirty = True
        # ok, we couldn't match the hunk. Lets look for offsets and fuzz it
        self.hash = {}
        for x, s in enumerate(self.lines):
            self.hash.setdefault(s, []).append(x)
                old, oldstart, new, newstart = h.fuzzit(fuzzlen, toponly)
                oldstart = oldstart + self.offset + self.skew
                oldstart = min(oldstart, len(self.lines))
                if old:
                    cand = self.findlines(old[0][1:], oldstart)
                else:
                    # Only adding lines with no or fuzzed context, just
                    # take the skew in account
                    cand = [oldstart]
                    if not old or diffhelpers.testhunk(old, self.lines, l) == 0:
                        self.lines[l : l + len(old)] = new
                        self.offset += len(new) - len(old)
                        self.dirty = True
    def close(self):
        if self.dirty:
            self.writelines(self.fname, self.lines, self.mode)
        self.write_rej()
        return len(self.rej)

    def __init__(self, desc, num, lr, context):
        nh = hunk(self.desc, self.number, None, None)
        self.starta, self.lena, self.startb, self.lenb = m.groups()
        diffhelpers.addlines(lr, self.hunk, self.lena, self.lenb, self.a,
                             self.b)
        self._fixnewline(lr)
        self.starta, aend = m.groups()
                # lines addition, old block is empty
        self.startb, bend = m.groups()
                # XXX: the only way to hit this is with an invalid line range.
                # The no-eol marker is not counted in the line range, but I
                # guess there are diff(1) out there which behave differently.
                # line deletions, new block is empty and we hit EOF
                # line deletions, new block is empty
        self._fixnewline(lr)
    def _fixnewline(self, lr):
        l = lr.readline()
        if l.startswith('\ '):
            diffhelpers.fix_newline(self.hunk, self.a, self.b)
        else:
            lr.push(l)
    def _fuzzit(self, old, new, fuzz, toponly):
        fuzz = min(fuzz, len(old))
            bot = min(fuzz, bot)
            top = min(fuzz, top)
            return old[top:len(old) - bot], new[top:len(new) - bot], top
        return old, new, 0

    def fuzzit(self, fuzz, toponly):
        old, new, top = self._fuzzit(self.a, self.b, fuzz, toponly)
        oldstart = self.starta + top
        newstart = self.startb + top
        # zero length hunk ranges already have their start decremented
        if self.lena and oldstart > 0:
            oldstart -= 1
        if self.lenb and newstart > 0:
            newstart -= 1
        return old, oldstart, new, newstart

class binhunk(object):
    def __init__(self, lr, fname):
        self._fname = fname
        self._read(lr)
    def _read(self, lr):
        def getline(lr, hunk):
            l = lr.readline()
            hunk.append(l)
            return l.rstrip('\r\n')

        while True:
            line = getline(lr, self.hunk)
            if not line:
                raise PatchError(_('could not extract "%s" binary data')
                                 % self._fname)
            if line.startswith('literal '):
                break
        line = getline(lr, self.hunk)
            try:
                dec.append(base85.b85decode(line[1:])[:l])
            except ValueError, e:
                raise PatchError(_('could not decode "%s" binary patch: %s')
                                 % (self._fname, str(e)))
            line = getline(lr, self.hunk)
            raise PatchError(_('"%s" length is %d bytes, should be %d')
                             % (self._fname, len(text), size))
def pathstrip(path, strip):
    pathlen = len(path)
    i = 0
    if strip == 0:
        return '', path.rstrip()
    count = strip
    while count > 0:
        i = path.find('/', i)
        if i == -1:
            raise PatchError(_("unable to strip away %d of %d dirs from %s") %
                             (count, strip, path))
        i += 1
        # consume '//' in the path
        while i < pathlen - 1 and path[i] == '/':
        count -= 1
    return path[:i].lstrip(), path[i:].rstrip()
def makepatchmeta(backend, afile_orig, bfile_orig, hunk, strip):
    create = nulla and hunk.starta == 0 and hunk.lena == 0
    remove = nullb and hunk.startb == 0 and hunk.lenb == 0
    gooda = not nulla and backend.exists(afile)
        goodb = not nullb and backend.exists(bfile)
    missing = not goodb and not gooda and not create
    # some diff programs apparently produce patches where the afile is
    # not /dev/null, but afile starts with bfile
    if (missing and abasedir == bbasedir and afile.startswith(bfile)
        and hunk.starta == 0 and hunk.lena == 0):
        create = True
        missing = False
    gp = patchmeta(fname)
    if create:
        gp.op = 'ADD'
    elif remove:
        gp.op = 'DELETE'
    return gp
    gitlr = linereader(fp)
    gitpatches = readgitpatch(gitlr)
    return gitpatches
def iterhunks(fp):
    emitfile = newfile = False
    gitpatches = None
        if state == BFILE and (
            (not context and x[0] == '@')
            or (context is not False and x.startswith('***************'))
            or x.startswith('GIT binary patch')):
            gp = None
            if (gitpatches and
                gitpatches[-1].ispatching(afile, bfile)):
                gp = gitpatches.pop()
            if x.startswith('GIT binary patch'):
                h = binhunk(lr, gp.path)
            else:
                h = hunk(x, hunknum + 1, lr, context)
                yield 'file', (afile, bfile, h, gp and gp.copy() or None)
            yield 'hunk', h
        elif x.startswith('diff --git a/'):
            m = gitre.match(x.rstrip(' \r\n'))
            if not m:
                continue
            if gitpatches is None:
                # scan whole input for git metadata
                gitpatches = scangitpatch(lr, x)
                yield 'git', [g.copy() for g in gitpatches
                              if g.op in ('COPY', 'RENAME')]
                gitpatches.reverse()
            afile = 'a/' + m.group(1)
            bfile = 'b/' + m.group(2)
            while gitpatches and not gitpatches[-1].ispatching(afile, bfile):
                gp = gitpatches.pop()
                yield 'file', ('a/' + gp.path, 'b/' + gp.path, None, gp.copy())
            if not gitpatches:
                raise PatchError(_('failed to synchronize metadata for "%s"')
                                 % afile[2:])
            gp = gitpatches[-1]
            newfile = True
            newfile = False
    while gitpatches:
        gp = gitpatches.pop()
        yield 'file', ('a/' + gp.path, 'b/' + gp.path, None, gp.copy())
def applydiff(ui, fp, backend, store, strip=1, eolmode='strict'):
    """Reads a patch from fp and tries to apply it.
    Returns 0 for a clean patch, -1 if any rejects were found and 1 if
    there was any fuzz.
    return _applydiff(ui, fp, patchfile, backend, store, strip=strip,
                      eolmode=eolmode)

def _applydiff(ui, fp, patcher, backend, store, strip=1,
               eolmode='strict'):

    def pstrip(p):
        return pathstrip(p, strip - 1)[1]

    for state, values in iterhunks(fp):
            ret = current_file.apply(values)
            if ret > 0:
                err = 1
            if current_file:
                rejects += current_file.close()
                current_file = None
            afile, bfile, first_hunk, gp = values
            if gp:
                gp.path = pstrip(gp.path)
                if gp.oldpath:
                    gp.oldpath = pstrip(gp.oldpath)
            else:
                gp = makepatchmeta(backend, afile, bfile, first_hunk, strip)
            if gp.op == 'RENAME':
                backend.unlink(gp.oldpath)
            if not first_hunk:
                if gp.op == 'DELETE':
                    backend.unlink(gp.path)
                    continue
                data, mode = None, None
                if gp.op in ('RENAME', 'COPY'):
                    data, mode = store.getfile(gp.oldpath)[:2]
                if gp.mode:
                    mode = gp.mode
                    if gp.op == 'ADD':
                        # Added files without content have no hunk and
                        # must be created
                        data = ''
                if data or mode:
                    if (gp.op in ('ADD', 'RENAME', 'COPY')
                        and backend.exists(gp.path)):
                        raise PatchError(_("cannot create %s: destination "
                                           "already exists") % gp.path)
                    backend.setfile(gp.path, data, mode, gp.oldpath)
                continue
                current_file = patcher(ui, gp, backend, store,
                                       eolmode=eolmode)
            except PatchError, inst:
                ui.warn(str(inst) + '\n')
                current_file = None
            for gp in values:
                path = pstrip(gp.oldpath)
                try:
                    data, mode = backend.getfile(path)
                except IOError, e:
                    if e.errno != errno.ENOENT:
                        raise
                    # The error ignored here will trigger a getfile()
                    # error in a place more appropriate for error
                    # handling, and will not interrupt the patching
                    # process.
                else:
                    store.setfile(path, data, mode)
    if current_file:
        rejects += current_file.close()
def _externalpatch(ui, repo, patcher, patchname, strip, files,
                   similarity):
    args = []
    cwd = repo.root
    try:
        for line in fp:
            line = line.rstrip()
            ui.note(line + '\n')
            if line.startswith('patching file '):
                pf = util.parsepatchoutput(line)
                printed_file = False
                files.add(pf)
            elif line.find('with fuzz') >= 0:
                fuzz = True
                if not printed_file:
                    ui.warn(pf + '\n')
                    printed_file = True
                ui.warn(line + '\n')
            elif line.find('saving rejects to file') >= 0:
                ui.warn(line + '\n')
            elif line.find('FAILED') >= 0:
                if not printed_file:
                    ui.warn(pf + '\n')
                    printed_file = True
                ui.warn(line + '\n')
    finally:
        if files:
            cfiles = list(files)
            cwd = repo.getcwd()
            if cwd:
                cfiles = [util.pathto(repo.root, cwd, f)
                          for f in cfiles]
            scmutil.addremove(repo, cfiles, similarity=similarity)
                         util.explainexit(code)[0])
def patchbackend(ui, backend, patchobj, strip, files=None, eolmode='strict'):
        files = set()
        raise util.Abort(_('unsupported line endings type: %s') % eolmode)
    store = filestore()
        ret = applydiff(ui, fp, backend, store, strip=strip,
                        eolmode=eolmode)
        files.update(backend.close())
        store.close()
        raise PatchError(_('patch failed to apply'))
def internalpatch(ui, repo, patchobj, strip, files=None, eolmode='strict',
                  similarity=0):
    """use builtin patch to apply <patchobj> to the working directory.
    returns whether patch was applied with fuzz factor."""
    backend = workingbackend(ui, repo, similarity)
    return patchbackend(ui, backend, patchobj, strip, files, eolmode)

def patchrepo(ui, repo, ctx, store, patchobj, strip, files=None,
              eolmode='strict'):
    backend = repobackend(ui, repo, ctx, store)
    return patchbackend(ui, backend, patchobj, strip, files, eolmode)

def makememctx(repo, parents, text, user, date, branch, files, store,
               editor=None):
    def getfilectx(repo, memctx, path):
        data, (islink, isexec), copied = store.getfile(path)
        return context.memfilectx(path, data, islink=islink, isexec=isexec,
                                  copied=copied)
    extra = {}
    if branch:
        extra['branch'] = encoding.fromlocal(branch)
    ctx =  context.memctx(repo, parents, text, files, getfilectx, user,
                          date, extra)
    if editor:
        ctx._text = editor(repo, ctx, [])
    return ctx

def patch(ui, repo, patchname, strip=1, files=None, eolmode='strict',
          similarity=0):
        files = set()
            return _externalpatch(ui, repo, patcher, patchname, strip,
                                  files, similarity)
        return internalpatch(ui, repo, patchname, strip, files, eolmode,
                             similarity)
        raise util.Abort(str(err))
def changedfiles(ui, repo, patchpath, strip=1):
    backend = fsbackend(ui, repo.root)
    fp = open(patchpath, 'rb')
    try:
        changed = set()
        for state, values in iterhunks(fp):
            if state == 'file':
                afile, bfile, first_hunk, gp = values
                if gp:
                    gp.path = pathstrip(gp.path, strip - 1)[1]
                    if gp.oldpath:
                        gp.oldpath = pathstrip(gp.oldpath, strip - 1)[1]
                else:
                    gp = makepatchmeta(backend, afile, bfile, first_hunk, strip)
                changed.add(gp.path)
                if gp.op == 'RENAME':
                    changed.add(gp.oldpath)
            elif state not in ('hunk', 'git'):
                raise util.Abort(_('unsupported parser state: %s') % state)
        return changed
    finally:
        fp.close()
def diffopts(ui, opts=None, untrusted=False, section='diff'):
    def get(key, name=None, getter=ui.configbool):
        return ((opts and opts.get(key)) or
                getter(section, name or key, None, untrusted=untrusted))
    return mdiff.diffopts(
        text=opts and opts.get('text'),
        git=get('git'),
        nodates=get('nodates'),
        showfunc=get('show_function', 'showfunc'),
        ignorews=get('ignore_all_space', 'ignorews'),
        ignorewsamount=get('ignore_space_change', 'ignorewsamount'),
        ignoreblanklines=get('ignore_blank_lines', 'ignoreblanklines'),
        context=get('unified', getter=ui.config))

         losedatafn=None, prefix=''):

    prefix is a filename prefix that is prepended to all filenames on
    display (used for subrepos).
        node1 = repo.dirstate.p1()
        order = util.deque()
                    del cache[order.popleft()]
    hexfunc = repo.ui.debugflag and hex or short
    revs = [hexfunc(node) for node in [node1, node2] if node]
        copy = copies.pathcopies(ctx1, ctx2)
    def difffn(opts, losedata):
        return trydiff(repo, revs, ctx1, ctx2, modified, added, removed,
                       copy, getfilectx, opts, losedata, prefix)
                    raise GitDiffRequired
def difflabel(func, *args, **kw):
    '''yields 2-tuples of (output, label) based on the output of func()'''
    headprefixes = [('diff', 'diff.diffline'),
                    ('copy', 'diff.extended'),
                    ('rename', 'diff.extended'),
                    ('old', 'diff.extended'),
                    ('new', 'diff.extended'),
                    ('deleted', 'diff.extended'),
                    ('---', 'diff.file_a'),
                    ('+++', 'diff.file_b')]
    textprefixes = [('@', 'diff.hunk'),
                    ('-', 'diff.deleted'),
                    ('+', 'diff.inserted')]
    head = False
    for chunk in func(*args, **kw):
        lines = chunk.split('\n')
        for i, line in enumerate(lines):
            if i != 0:
                yield ('\n', '')
            if head:
                if line.startswith('@'):
                    head = False
            else:
                if line and line[0] not in ' +-@\\':
                    head = True
            stripline = line
            if not head and line and line[0] in '+-':
                # highlight trailing whitespace, but only in changed lines
                stripline = line.rstrip()
            prefixes = textprefixes
            if head:
                prefixes = headprefixes
            for prefix, label in prefixes:
                if stripline.startswith(prefix):
                    yield (stripline, label)
                    break
            else:
                yield (line, '')
            if line != stripline:
                yield (line[len(stripline):], 'diff.trailingwhitespace')

def diffui(*args, **kw):
    '''like diff(), but yields 2-tuples of (output, label) for ui.write()'''
    return difflabel(diff, *args, **kw)
            copy, getfilectx, opts, losedatafn, prefix):

    def join(f):
        return posixpath.join(prefix, f)

    def addmodehdr(header, omode, nmode):
        if omode != nmode:
            header.append('old mode %s\n' % omode)
            header.append('new mode %s\n' % nmode)

    def addindexmeta(meta, revs):
        if opts.git:
            i = len(revs)
            if i==2:
                meta.append('index %s..%s\n' % tuple(revs))
            elif i==3:
                meta.append('index %s,%s..%s\n' % tuple(revs))

    def gitindex(text):
        if not text:
            return hex(nullid)
        l = len(text)
        s = util.sha1('blob %d\0' % l)
        s.update(text)
        return s.hexdigest()

    def diffline(a, b, revs):
        if opts.git:
            line = 'diff --git a/%s b/%s\n' % (a, b)
        elif not repo.ui.quiet:
            if revs:
                revinfo = ' '.join(["-r %s" % rev for rev in revs])
                line = 'diff %s %s\n' % (revinfo, a)
            else:
                line = 'diff %s\n' % a
        else:
            line = ''
        return line
                        addmodehdr(header, omode, mode)
                        header.append('%s from %s\n' % (op, join(a)))
                        header.append('%s to %s\n' % (op, join(f)))
                # In theory, if tn was copied or renamed we should check
                # if the source is binary too but the copy record already
                # forces git mode.
                        if util.binary(to):
                            dodiff = 'binary'
                elif not to or util.binary(to):
                    addmodehdr(header, gitmode[oflag], gitmode[nflag])
            if opts.git or revs:
                header.insert(0, diffline(join(a), join(b), revs))
                text = mdiff.b85diff(to, tn)
                if text:
                    addindexmeta(header, [gitindex(to), gitindex(tn)])
                                    join(a), join(b), opts=opts)
def diffstatsum(stats):
    maxfile, maxtotal, addtotal, removetotal, binary = 0, 0, 0, 0, False
    for f, a, r, b in stats:
        maxfile = max(maxfile, encoding.colwidth(f))
        maxtotal = max(maxtotal, a + r)
        addtotal += a
        removetotal += r
        binary = binary or b

    return maxfile, maxtotal, addtotal, removetotal, binary
    diffre = re.compile('^diff .*-r [a-z0-9]+\s(.*)$')

    results = []
    filename, adds, removes, isbinary = None, 0, 0, False

    def addresult():
        if filename:
            results.append((filename, adds, removes, isbinary))

            addresult()
            adds, removes, isbinary = 0, 0, False
            if line.startswith('diff --git a/'):
            elif line.startswith('diff -r'):
                filename = diffre.search(line).group(1)
        elif line.startswith('+') and not line.startswith('+++ '):
        elif line.startswith('-') and not line.startswith('--- '):
        elif (line.startswith('GIT binary patch') or
              line.startswith('Binary file')):
            isbinary = True
    addresult()
    return results
    stats = diffstatdata(lines)
    maxname, maxtotal, totaladds, totalremoves, hasbinary = diffstatsum(stats)
        if isbinary:
        output.append(' %s%s |  %*s %s%s\n' %
                      (filename, ' ' * (maxname - encoding.colwidth(filename)),
                       countwidth, count, pluses, minuses))
        output.append(_(' %d files changed, %d insertions(+), '
                        '%d deletions(-)\n')

def diffstatui(*args, **kw):
    '''like diffstat(), but yields 2-tuples of (output, label) for
    ui.write()
    '''

    for line in diffstat(*args, **kw).splitlines():
        if line and line[-1] in '+-':
            name, graph = line.rsplit(' ', 1)
            yield (name + ' ', '')
            m = re.search(r'\++', graph)
            if m:
                yield (m.group(0), 'diffstat.inserted')
            m = re.search(r'-+', graph)
            if m:
                yield (m.group(0), 'diffstat.deleted')
        else:
            yield (line, '')
        yield ('\n', '')