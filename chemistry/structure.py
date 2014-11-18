"""
This module contains the core base class for all of the chemical structures with
various topological and force field features.

Author: Jason Swails
Date: November 10, 2014
"""
try:
    import bz2
except ImportError:
    bz2 = None
from chemistry.exceptions import PDBError, PDBWarning
from chemistry.periodic_table import AtomicNum, Mass
from chemistry.topologyobjects import TrackedList, AtomList, ResidueList, Atom
try:
    import gzip
except ImportError:
    gzip = None
import re
import warnings

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# Private attributes and methods

relatere = re.compile(r'RELATED ID: *(\w+) *RELATED DB: *(\w+)', re.I)

def _compare_atoms(old_atom, new_atom, resname, resid, chain):
    """
    Compares two atom instances, along with the residue name, number, and chain
    identifier, to determine if two atoms are actually the *same* atom, but
    simply different conformations

    Parameters
    ----------
    old_atom : Atom
        The original atom that has been added to the structure already
    new_atom : Atom
        The new atom that we want to see if it is the same as the old atom
    resname : str
        The name of the residue that the new atom would belong to
    resid : int
        The number of the residue that the new atom would belong to
    chain : str
        The chain identifier that the new atom would belong to

    Returns
    -------
    True if they are the same atom, False otherwise
    """
    if old_atom.name != new_atom.name: return False
    if old_atom.residue.name != resname: return False
    if old_atom.residue.number != resid: return False
    if old_atom.residue.chain != chain.strip(): return False
    return True

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class Structure(object):
    """
    A chemical structure composed of atoms, bonds, angles, torsions, and other
    topological features

    Attributes
    ----------
    atoms : AtomList
        List of all atoms in the structure
    residues : ResidueList
        List of all residues in the structure
    bonds : TrackedList(Bond)
        List of all bonds in the structure
    angles : TrackedList(Angle)
        List of all angles in the structure
    dihedrals : TrackedList(Dihedral)
        List of all dihedrals in the structure -- only one term per dihedral, so
        multi-term dihedral parameters will have the same 4 atoms appear
        multiple times in the list
    urey_bradleys : TrackedList(UreyBradley)
        List of all Urey-Bradley angle bends in the structure
    impropers : TrackedList(Improper)
        List of all CHARMM-style improper torsions in the structure
    cmaps : TrackedList(Cmap)
        List of all CMAP objects in the structure
    trigonal_angles : TrackedList(TrigonalAngle)
        List of all AMOEBA-style trigonal angles in the structure
    out_of_plane_bends : TrackedList(OutOfPlaneBends)
        List of all AMOEBA-style out-of-plane bending angles
    pi_torsions : TrackedList(PiTorsion)
        List of all AMOEBA-style pi-torsion angles
    stretch_bends : TrackedList(StretchBend)
        List of all AMOEBA-style stretch-bend compound bond/angle terms
    torsion_torsions : TrackedList(TorsionTorsion)
        List of all AMOEBA-style coupled torsion-torsion terms
    chiral_frames : TrackedList(ChiralFrame)
        List of all AMOEBA-style chiral frames defined in the structure
    multipole_frames : TrackedList(MultipoleFrame)
        List of all AMOEBA-style multipole frames defined in the structure
    adjusts : TrackedList(NonbondedException)
        List of all AMOEBA-style nonbonded pair-exception rules
    acceptors : TrackedList(AcceptorDonor)
        List of all H-bond acceptors, if that information is present
    donors : TrackedList(AcceptorDonor)
        List of all H-bond donors, if that information is present
    groups : TrackedList(Group)
        List of all CHARMM-style GROUP objects (whatever those are used for)
    box : list of 6 floats
        Box dimensions (a, b, c, alpha, beta, gamma) for the unit cell. If no
        box is defined, `box` is set to `None`

    This class also has a handful of type lists for each of the attributes above
    (excluding `atoms`, `residues`, `chiral_frames`, and `multipole_frames`).
    They are all TrackedList instances that are designed to hold the relevant
    parameter type. The list is:
        bond_types, angle_types, dihedral_types, urey_bradley_types,
        improper_types, cmap_types, trigonal_angle_types,
        out_of_plane_bend_types, pi_torsion_types, stretch_bend_types,
        torsion_torsion_types, adjust_types

    Notes
    -----
    dihedral_types _may_ be a list of DihedralType instances, since torsion
    profiles are often represented by a Fourier series with multiple terms
    """
    #===================================================

    def __init__(self):

        # Topological object lists
        self.atoms = AtomList()
        self.residues = ResidueList()
        self.bonds = TrackedList()
        self.angles = TrackedList()
        self.dihedrals = TrackedList()
        self.urey_bradleys = TrackedList()
        self.impropers = TrackedList()
        self.cmaps = TrackedList()
        self.trigonal_angles = TrackedList()
        self.out_of_plane_bends = TrackedList()
        self.pi_torsions = TrackedList()
        self.stretch_bends = TrackedList()
        self.torsion_torsions = TrackedList()
        self.chiral_frames = TrackedList()
        self.multipole_frames = TrackedList()
        self.adjusts = TrackedList()
        # Extraneous information stored in CHARMM PSF files... not used as far
        # as I can tell for much of anything
        self.acceptors = TrackedList()
        self.donors = TrackedList()
        self.groups = TrackedList()

        # Parameter type lists
        self.bond_types = TrackedList()
        self.angle_types = TrackedList()
        self.dihedral_types = TrackedList()
        self.urey_bradley_types = TrackedList()
        self.improper_types = TrackedList()
        self.cmap_types = TrackedList()
        self.trigonal_angle_types = TrackedList()
        self.out_of_plane_bend_types = TrackedList()
        self.pi_torsion_types = TrackedList()
        self.stretch_bend_types = TrackedList()
        self.torsion_torsion_types = TrackedList()
        self.adjust_types = TrackedList()

        self.box = None

    #===================================================

    def is_changed(self):
        """ Determines if any of the topology has changed for this structure """
        return (self.atoms.changed or self.residues.changed or
                self.bonds.changed or self.trigonal_angles.changed or
                self.dihedrals.changed or self.urey_bradleys.changed or
                self.impropers.changed or self.cmaps.changed or
                self.angles.changed or self.out_of_plane_bends.changed or
                self.pi_torsions.changed or self.stretch_bends.changed or
                self.torsion_torsions.changed or self.chiral_frames.changed or
                self.multipole_frames.changed or self.adjusts.changed or
                self.acceptors.changed or self.donors.changed or
                self.groups.changed or self.bond_types.changed or
                self.angle_types.changed or self.dihedral_types.changed or
                self.urey_bradley_types.changed or self.cmap_types.changed or
                self.improper_types.changed or self.adjust_types.changed or
                self.trigonal_angle_types.changed or
                self.out_of_plane_bends.changed or
                self.stretch_bend_types.changed or
                self.torsion_torsion_types.changed or
                self.pi_torsion_types.changed)

    #===================================================

    def unchange(self):
        """ Toggles all lists so that they do not indicate any changes """
        self.atoms.changed = False
        self.residues.changed = False
        self.bonds.changed = False
        self.angles.changed = False
        self.dihedrals.changed = False
        self.urey_bradleys.changed = False
        self.impropers.changed = False
        self.cmaps.changed = False
        self.trigonal_angles.changed = False
        self.out_of_plane_bends.changed = False
        self.pi_torsions.changed = False
        self.stretch_bends.changed = False
        self.torsion_torsions.changed = False
        self.chiral_frames.changed = False
        self.multipole_frames.changed = False
        self.adjusts.changed = False
        self.acceptors.changed = False
        self.donors.changed = False
        self.groups.changed = False

        # Parameter type lists
        self.bond_types.changed = False
        self.angle_types.changed = False
        self.dihedral_types.changed = False
        self.urey_bradley_types.changed = False
        self.improper_types.changed = False
        self.cmap_types.changed = False
        self.trigonal_angle_types.changed = False
        self.out_of_plane_bend_types.changed = False
        self.pi_torsion_types.changed = False
        self.stretch_bend_types.changed = False
        self.torsion_torsion_types.changed = False
        self.adjust_types.changed = False

    #===================================================

    def prune_empty_terms(self):
        """
        Looks through all of the topological lists and gets rid of terms
        in which at least one of the atoms is None or has an `idx` attribute set
        to -1 (indicating that it has been removed from the `atoms` atom list)
        """
        self._prune_empty_bonds()
        self._prune_empty_angles()
        self._prune_empty_dihedrals()
        self._prune_empty_ureys()
        self._prune_empty_impropers()
        self._prune_empty_cmaps()
        self._prune_empty_trigonal_angles()
        self._prune_empty_out_of_plane_bends()
        self._prune_empty_pi_torsions()
        self._prune_empty_stretch_bends()
        self._prune_empty_torsion_torsions()
        self._prune_empty_chiral_frames()
        self._prune_empty_multipole_frames()
        self._prune_empty_adjusts()

    #===================================================

    def _prune_empty_bonds(self):
        """ Gets rid of any empty bonds """
        for i in reversed(xrange(len(self.bonds))):
            bond = self.bonds[i]
            if bond.atom1 is None and bond.atom2 is None:
                del self.bonds[i]
            elif bond.atom1.idx == -1 or bond.atom2.idx == -1:
                bond.delete()
                del self.bonds[i]

    #===================================================

    def _prune_empty_angles(self):
        """ Gets rid of any empty angles """
        for i in reversed(xrange(len(self.angles))):
            angle = self.angles[i]
            if (angle.atom1 is None and angle.atom2 is None and
                    angle.atom3 is None):
                del self.angles[i]
            elif (angle.atom1.idx == -1 or angle.atom2.idx == -1 or
                    angle.atom3.idx == -1):
                angle.delete()
                del self.angles[i]

    #===================================================

    def _prune_empty_dihedrals(self):
        """ Gets rid of any empty dihedrals """
        for i in reversed(xrange(len(self.dihedrals))):
            dihed = self.dihedrals[i]
            if (dihed.atom1 is None and dihed.atom2 is None and
                    dihed.atom3 is None and dihed.atom4 is None):
                del self.dihedrals[i]
            elif (dihed.atom1.idx == -1 or dihed.atom2.idx == -1 or
                    dihed.atom3.idx == -1 or dihed.atom4.idx == -1):
                dihed.delete()
                del self.dihedrals[i]

    #===================================================

    def _prune_empty_ureys(self):
        """ Gets rid of any empty Urey-Bradley terms """
        for i in reversed(xrange(len(self.urey_bradleys))):
            ub = self.urey_bradleys[i]
            if ub.atom1 is None and ub.atom2 is None:
                del self.urey_bradleys[i]
            elif ub.atom1.idx == -1 or ub.atom2.idx == -1:
                ub.delete()
                del self.urey_bradleys[i]

    #===================================================

    def _prune_empty_impropers(self):
        """ Gets rid of any empty improper torsions """
        for i in reversed(xrange(len(self.impropers))):
            imp = self.impropers[i]
            if (imp.atom1 is None and imp.atom2 is None and imp.atom3 is None
                    and imp.atom4 is None):
                del self.impropers[i]
            elif (imp.atom1.idx == -1 or imp.atom2.idx == -1 or
                    imp.atom3.idx == -1 or imp.atom4.idx == -1):
                imp.delete()
                del self.impropers[i]

    #===================================================

    def _prune_empty_cmaps(self):
        """ Gets rid of any empty CMAP terms """
        for i in reversed(xrange(len(self.cmaps))):
            cmap = self.cmaps[i]
            if (cmap.atom1 is None and cmap.atom2 is None and cmap.atom3 is None
                    and cmap.atom4 is None and cmap.atom5 is None):
                del self.cmaps[i]
            elif (cmap.atom1.idx == -1 or cmap.atom2.idx == -1 or
                    cmap.atom3.idx == -1 or cmap.atom4.idx == -1 or
                    cmap.atom5.idx == -1):
                cmap.delete()
                del self.cmaps[i]

    #===================================================

    def _prune_empty_trigonal_angles(self):
        """ Gets rid of any empty trigonal angles """
        for i in reversed(xrange(len(self.trigonal_angles))):
            ta = self.trigonal_angles[i]
            if (ta.atom1 is None and ta.atom2 is None and ta.atom3 is None and
                    ta.atom4 is None):
                del self.trigonal_angles[i]
            elif (ta.atom1.idx == -1 or ta.atom2.idx == -1 or
                    ta.atom3.idx == -1 or ta.atom4.idx == -1):
                # Not stored anywhere, no need to call delete()
                del self.trigonal_angles[i]

    #===================================================

    def _prune_empty_out_of_plane_bends(self):
        """ Gets rid of any empty out-of-plane bends """
        for i in reversed(xrange(len(self.out_of_plane_bends))):
            oop = self.out_of_plane_bends[i]
            if (oop.atom1 is None and oop.atom2 is None and oop.atom3 is None
                    and oop.atom4 is None):
                del self.out_of_plane_bends[i]
            elif (oop.atom1.idx == -1 or oop.atom2.idx == -1 or
                    oop.atom3.idx == -1 or oop.atom4.idx == -1):
                # Not stored anywhere, no need to call delete()
                del self.out_of_plane_bends[i]

    #===================================================

    def _prune_empty_pi_torsions(self):
        """ Gets rid of any empty pi-torsions """
        for i in reversed(xrange(len(self.pi_torsions))):
            pit = self.pi_torsions[i]
            if (pit.atom1 is None and pit.atom2 is None and
                    pit.atom3 is None and pit.atom4 is None and
                    pit.atom5 is None and pit.atom6 is None):
                del self.pi_torsions[i]
            elif (pit.atom1.idx == -1 or pit.atom2.idx == -1 or
                    pit.atom3.idx == -1 or pit.atom4.idx == -1 or
                    pit.atom5.idx == -1 or pit.atom6.idx == -1):
                # Not stored anywhere, no need to call delete()
                del self.pi_torsions[i]

    #===================================================

    def _prune_empty_stretch_bends(self):
        """ Gets rid of any empty stretch-bend terms """
        for i in reversed(xrange(len(self.stretch_bends))):
            sb = self.stretch_bends[i]
            if sb.atom1 is None and sb.atom2 is None and sb.atom3 is None:
                del self.stretch_bends[i]
            elif (sb.atom1.idx == -1 or sb.atom2.idx == -1 or
                    sb.atom3.idx == -1):
                # Not stored anywhere, no need to call delete()
                del self.stretch_bends[i]

    #===================================================

    def _prune_empty_torsion_torsions(self):
        """ Gets rid of any empty torsion-torsion terms """
        for i in reversed(xrange(len(self.torsion_torsions))):
            tt = self.torsion_torsions[i]
            if (tt.atom1 is None and tt.atom2 is None and tt.atom3 is None
                    and tt.atom4 is None and tt.atom5 is None):
                del self.torsion_torsions[i]
            elif (tt.atom1.idx == -1 or tt.atom2.idx == -1 or
                    tt.atom3.idx == -1 or tt.atom4.idx == -1 or
                    tt.atom5.idx == -1):
                tt.delete()
                del self.torsion_torsions[i]

    #===================================================

    def _prune_empty_chiral_frames(self):
        """ Gets rid of any empty chiral frame terms """
        for i in reversed(xrange(len(self.chiral_frames))):
            cf = self.chiral_frames[i]
            if cf.atom1 is None or cf.atom2 is None:
                del self.chiral_frames[i]
            elif cf.atom1.idx == -1 or cf.atom2.idx == -1:
                del self.chiral_frames[i]

    #===================================================

    def _prune_empty_multipole_frames(self):
        """ Gets rid of any empty multipole frame terms """
        for i in reversed(xrange(len(self.multipole_frames))):
            mf = self.multipole_frames[i]
            if mf.atom is None or mf.atom.idx == -1:
                del self.multipole_frames[i]

    #===================================================

    def _prune_empty_adjusts(self):
        """ Gets rid of any empty nonbonded exception adjustments """
        for i in reversed(xrange(len(self.adjusts))):
            adj = self.adjusts[i]
            if adj.atom1 is None or adj.atom2 is None:
                del self.adjusts[i]
            elif adj.atom1.idx == -1 or adj.atom2.idx == -1:
                del self.adjusts[i]

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

def read_PDB(filename):
    """
    Read a PDB file and return a populated `Structure` class

    Parameters
    ----------
    filename : str or file-like
        Name of PDB file to read, or a file-like object that can iterate over
        the lines of a PDB. Compressed file names can be specified and are
        determined by file-name extension (e.g., file.pdb.gz, file.pdb.bz2)

    Metadata
    --------
    The PDB parser also adds metadata to the returned Structure object that may
    be present in the PDB file

    experimental : str
        EXPDTA record
    journal : str
        JRNL record
    authors : str
        AUTHOR records
    keywords : str
        KEYWDS records
    doi : str
        DOI from the JRNL record
    pmid : str
        PMID from the JRNL record
    journal_authors : str
        Author info from the JRNL record
    volume : str
        Volume of the published article from the JRNL record
    page : str
        Page of the published article from the JRNL record
    title : str
        TITL section of the JRNL record
    year : int=None
        Year that the article was published, from the JRNL record
    related_entries : list of (str, str)
        List of entries in other databases 

    Returns
    -------
    structure
    
    structure : Structure
        The Structure object initialized with all of the information from the
        PDB file.  No bonds or other topological features are added by default.

    Notes
    -----
    The returned structure has an extra attribute, pdbxyz, that contains all of
    the coordinates for all of the frames in the PDB file as a list of NATOM*3
    lists.
    """
    global relatere
    if isinstance(filename, basestring):
        own_handle = True
        if filename.endswith('.gz'):
            if gzip is None:
                raise ImportError('gzip is not available for compressed PDB')
            fileobj = gzip.open(filename, 'r')
        elif filename.endswith('.bz2'):
            if bz2 is None:
                raise ImportError('bz2 is not available for compressed PDB')
            fileobj = bz2.BZ2File(filename, 'r')
        else:
            fileobj = open(filename, 'r')
    else:
        own_handle = False
        fileobj = filename

    struct = Structure()
    # Add metadata fields
    struct.experimental = struct.journal = struct.authors = struct.keywords = ''
    struct.doi = struct.pmid = struct.journal_authors = struct.volume_page = ''
    struct.title = ''
    struct.year = None
    struct.related_entries = []
    modelno = 1 # For PDB files with multiple MODELs
    atomno = 0
    coordinates = []
    all_coordinates = []

    # Support hexadecimal numbering like that printed by VMD
    last_atom = Atom()
    last_resid = 1
    res_hex = False
    atom_hex = False

    try:
        for line in fileobj:
            try:
                line = line.encode('ascii')
            except AttributeError:
                # ssume this is a string in Py3 which doesn't have 'decode'
                pass
            rec = line[:6]
            if rec == 'ATOM  ' or rec == 'HETATM':
                atomno += 1
                atnum, atname, altloc = line[6:11], line[12:16], line[16]
                resname, chain, resid = line[17:20], line[21], line[22:26]
                inscode = line[26]
                x, y, z = line[30:38], line[38:46], line[47:54]
                occupancy, bfactor = line[54:60], line[60:66]
                elem, chg = line[76:78], line[78:80]
                elem = '%-2s' % elem # Make sure we have at least 2 characters
                if elem[0] == ' ': elem = elem[1] + ' '
                try:
                    atsym = (elem[0] + elem[1].lower()).strip()
                    atomic_number = AtomicNum[atsym]
                    mass = Mass[atsym]
                except KeyError:
                    # Now try based on the atom name... but don't try too hard
                    # (e.g., don't try to differentiate b/w Ca and C)
                    try:
                        atomic_number = AtomicNum[atname.strip()[0].upper()]
                        mass = Mass[atname.strip()[0].upper()]
                    except KeyError:
                        try:
                            sym = atname.strip()[:2]
                            sym = '%s%s' % (sym[0].upper(), sym[0].lower())
                            atomic_number = AtomicNum[sym]
                            mass = Mass[sym]
                        except KeyError:
                            atomic_number = 0 # give up
                            mass = 0.0
                try:
                    bfactor = float(bfactor)
                except ValueError:
                    bfactor = 0.0
                try:
                    occupancy = float(occupancy)
                except ValueError:
                    occupancy = 0.0
                # Figure out what my residue number is and see if the PDB is
                # outputting residue numbers in hexadecimal (e.g., VMD)
                if last_resid >= 9999:
                    if not res_hex and resid == '9999':
                        resid = 9999
                    elif not res_hex:
                        res_hex = int(resid, 16) == 10000
                    # So now we know if we use hexadecimal or not. If we do,
                    # convert. Otherwise, stay put
                    if res_hex:
                        try:
                            resid = int(resid, 16)
                        except ValueError, e:
                            if resid == '****':
                                resid = None # Figure out by unique atoms
                            else:
                                raise e
                    else:
                        resid = int(resid)
                else:
                    resid = int(resid)
                # If the number has cycled, it too may be hexadecimal
                if atom_hex:
                    atnum = int(atnum, 16)
                else:
                    try:
                        atnum = int(atnum)
                    except ValueError:
                        atnum = int(atnum, 16)
                        atom_hex = True
                # It's possible that the residue number has cycled so much that
                # it is now filled with ****'s. In that case, start a new
                # residue if the current residue repeats the same atom name as
                # the 'last' residue. Do not worry about atom numbers going to
                # *****'s, since that is >1M atoms.
                if resid is None:
                    for atom in struct.residues[-1]:
                        if atom.name == atname:
                            resid = last_resid + 1
                            break
                if resid is None:
                    # Still part of the last residue
                    resid = last_resid
                last_resid = resid
                try:
                    chg = float(chg)
                except ValueError:
                    chg = 0
                atom = Atom(atomic_number=atomic_number, name=atname,
                            charge=chg, mass=mass, occupancy=occupancy,
                            bfactor=bfactor, altloc=altloc)
                atom.xx, atom.xy, atom.xz = float(x), float(y), float(z)
                if _compare_atoms(last_atom, atom, resname, resid, chain):
                    atom.residue = last_atom.residue
                    last_atom.other_locations[altloc] = atom
                    continue
                last_atom = atom
                if modelno == 1:
                    struct.residues.add_atom(atom, resname, resid,
                                             chain, inscode)
                    struct.atoms.append(atom)
                else:
                    try:
                        orig_atom = struct.atoms[atomno-1]
                    except IndexError:
                        raise PDBError('Atom %d differs in MODEL %d [%s %s vs. '
                                       '%s %s]' % (atomno, modelno,
                                       atom.residue.name, atom.name, resname,
                                       atname))
                    if (orig_atom.residue.name != resname.strip()
                            or orig_atom.name != atname.strip()):
                        raise PDBError('Atom %d differs in MODEL %d [%s %s vs. '
                                       '%s %s]' % (atomno, modelno,
                                       orig_atom.residue.name, orig_atom.name,
                                       resname, atname))
                coordinates.extend([atom.xx, atom.xy, atom.xz])
            elif rec.strip() == 'TER':
                if modelno == 1: last_atom.residue.ter = True
            elif rec == 'ENDMDL':
                # End the current model
                if len(struct.atoms) == 0:
                    raise PDBError('MODEL ended before any atoms read in')
                modelno += 1
                if len(struct.atoms)*3 != len(coordinates):
                    raise ValueError(
                            'Inconsistent atom numbers in some PDB models')
                all_coordinates.append(coordinates)
                atomno = 0
                coordinates = []
            elif rec == 'MODEL ':
                if modelno == 1 and len(struct.atoms) == 0: continue
                if len(coordinates) > 0:
                    if len(struct.atoms)*3 != len(coordinates):
                        raise ValueError(
                                'Inconsistent atom numbers in some PDB models')
                    warnings.warn('MODEL not explicitly ended', PDBWarning)
                    all_coordinates.append(coordinates)
                    coordinates = []
                modelno += 1
                atomno = 0
            elif rec == 'CRYST1':
                a = float(line[6:15])
                b = float(line[15:24])
                c = float(line[24:33])
                try:
                    A = float(line[33:40])
                    B = float(line[40:47])
                    C = float(line[47:54])
                except (IndexError, ValueError):
                    A = B = C = 90.0
                struct.box = [a, b, c, A, B, C]
            elif rec == 'EXPDTA':
                struct.experimental = line[6:].strip()
            elif rec == 'AUTHOR':
                struct.authors += line[10:].strip()
            elif rec == 'JRNL  ':
                part = line[12:16]
                if part == 'AUTH':
                    struct.journal_authors += line[19:].strip()
                elif part == 'TITL':
                    struct.title += ' %s' % line[19:].strip()
                elif part == 'REF ':
                    struct.journal += ' %s' % line[19:47].strip()
                    if not line[16:18].strip():
                        struct.volume = line[51:55].strip()
                        struct.page = line[56:61].strip()
                        try:
                            struct.year = int(line[62:66])
                        except ValueError:
                            pass
                elif part == 'PMID':
                    struct.pmid = line[19:].strip()
                elif part == 'DOI ':
                    struct.doi = line[19:].strip()
            elif rec == 'KEYWDS':
                struct.keywords += '%s,' % line[10:]
            elif rec == 'REMARK' and line[6:10] == ' 900':
                # Related entries
                rematch = relatere.match(line[11:])
                if rematch:
                    struct.related_entries.append(rematch.groups())
    finally:
        # Make sure our file is closed if we opened it
        if own_handle: fileobj.close()

    # Post-process some of the metadata to make it more reader-friendly
    struct.keywords = [s.strip() for s in struct.keywords.split(',')
                                        if s.strip()]
    struct.journal = struct.journal.strip()
    struct.title = struct.title.strip()

    struct.unchange()
    if coordinates:
        if len(coordinates) != 3*len(struct.atoms):
            raise ValueError('bad number of atoms in some PDB models')
        all_coordinates.append(coordinates)
    struct.pdbxyz = all_coordinates
    return struct

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

