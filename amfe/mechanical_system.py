# -*- coding: utf-8 -*-
"""
Created on Fri May  8 16:58:03 2015

@author: johannesr

Create mechanical system with default material parameters by:
my_system = amfe.MechanicalSystem()
If you want to use special material parameter, create mechanical system by e.g:
my_system = amfe.MechanicalSystem(E_modul=1000.0, poisson_ratio=0.15, 
                                  element_thickness=1.0, density=1.0)
"""

import numpy as np
import scipy as sp

from amfe.mesh import *
from amfe.element import *
from amfe.assembly import *
from amfe.boundary import *



# Anmerkungen (Fabian):
# - die Assembly-Klasse wird nach dem Einlesen des Netzes in der jeweiligen 
#   Netz-Einlese-Methode instanziert


class MechanicalSystem():
    '''
    Mase class for mechanical systems with the goal to black-box the routines
    of assembly and element selection.
    
    Attributes
    ----------
    mesh_class : instance of Mesh()
        Class handling the mesh. 
    assembly_class : instance of Assembly()
        Class handling the assembly. 
    dirichlet_class : instance of DirichletBoundary
        Class handling the Dirichlet boundary conditions. 
    neumann_class : instance of NeumannBoundary
        This boundary type is deprecated. 
    '''

    def __init__(self):
        '''
        '''      
        self.T_output = []
        self.u_output = []
        
        # instanciate the important classes needed for the system:
        self.mesh_class = Mesh()
        self.assembly_class = Assembly(self.mesh_class)
        self.dirichlet_class = DirichletBoundary(np.nan)
        self.neumann_class = NeumannBoundary(self.mesh_class.no_of_dofs, [])

        # make syntax a little bit leaner
        self.unconstrain_vec = self.dirichlet_class.unconstrain_vec
        self.constrain_vec = self.dirichlet_class.constrain_vec
        self.constrain_matrix = self.dirichlet_class.constrain_matrix
        
        pass

    def load_mesh_from_gmsh(self, msh_file, phys_group, material):
        '''
        Load the mesh from a msh-file generated by gmsh.

        Parameters
        ----------
        msh_file : str
            file name to an existing .msh file
        phys_group : int
            integer key of the physical group which is considered as the 
            mesh part 
        material : amfe.Material
            Material associated with the physical group to be computed
        
        Returns
        -------
        None
        '''
        self.mesh_class.import_msh(msh_file)
        self.mesh_class.load_group_to_mesh(phys_group, material)
        
        self.no_of_dofs = self.mesh_class.no_of_dofs
        self.no_of_dofs_per_node = self.mesh_class.no_of_dofs_per_node
        
        self.assembly_class.preallocate_csr()
        self.dirichlet_class.no_of_unconstrained_dofs = self.mesh_class.no_of_dofs
        



    def load_mesh_from_csv(self, node_list_csv, element_list_csv, 
                no_of_dofs_per_node=2, explicit_node_numbering=False, ele_type=False):
        '''
        Loads the mesh from two csv-files containing the node and the element list.

        Parameters
        ----------
        node_list_csv: str
            filename of the csv-file containing the coordinates of the nodes (x, y, z)
        element_list_csv: str
            filename of the csv-file containing the nodes which belong to one element
        no_of_dofs_per_node: int, optional
            degree of freedom per node as saved in the csv-file
        explicit_node_numbering : bool, optional
            flag stating, if the node numbers are explcitly numbered in the 
            csv file, i.e. if the first column gives the numbers of the nodes.
        ele_type: str
            Spezifiy elements type of the mesh (e.g. for a Tri-Mesh different
            elements types as Tri3, Tri4, Tri6 can be used)
            If not spezified value is set to 'False'

        Returns
        -------
        None

        Examples
        --------
        todo

        '''
        self.mesh_class.import_csv(node_list_csv, element_list_csv, 
                    explicit_node_numbering=explicit_node_numbering, ele_type=ele_type)
        
        self.no_of_dofs = self.mesh_class.no_of_dofs
        self.no_of_dofs_per_node = no_of_dofs_per_node
        
        self.assembly_class.preallocate_csr()

        # Initialize self.b_constraints here,
        # It does not make sence to call apply_dirichlet_boundaries() if the 
        # mechanical system has no dirichlet boundaries but self.b_constraints
        # has to be initialized since an error will occur later if 
        # self.b_constraints does not exist 
        self.b_constraints = sp.sparse.eye(self.no_of_dofs).tocsr()


    def apply_dirichlet_boundaries(self, key, coord, mesh_prop='phys_group'):
        '''
        Apply dirichlet-boundaries to the system.
        
        Parameters
        ----------
        key : int
            Key for mesh property which is to be chosen. Matches the group given 
            in the gmsh file. For help, the function mesh_information or 
            boundary_information gives the groups
        coord : str {'x', 'y', 'z', 'xy', 'xz', 'yz', 'xyz'}
            coordinates which should be fixed
        mesh_prop : str {'phys_group', 'geom_entity', 'el_type'}, optional
            label of which the element should be chosen from. Default is 
            'phys_group'. 
            
        Returns
        -------
        None
        '''
        self.mesh_class.select_dirichlet_bc(key, coord, mesh_prop)
        self.dirichlet_class.constrain_dofs(self.mesh_class.dofs_dirichlet)
#         self.no_of_dofs_constrained = self.b_constraints.shape[-1]

    def apply_neumann_boundaries(self, key, val, direct, time_func=None, 
                                 mesh_prop='phys_group'):
        '''
        Apply neumann boundaries to the system via skin elements. 
        
        Parameters
        ----------
        key : int
            Key of the physical domain to be chosen for the neumann bc
        val : float
            value for the pressure/traction onto the element
        direct : str {'normal', 'x_n', 'y_n', 'z_n', 'x', 'y', 'z'}
            direction, in which the traction should point at: 
            
            'normal'
                Pressure acting onto the normal face of the deformed configuration
            'x_n'
                Traction acting in x-direction proportional to the area 
            projected onto the y-z surface
            'y_n'
                Traction acting in y-direction proportional to the area 
                projected onto the x-z surface            
            'z_n'
                Traction acting in z-direction proportional to the area 
                projected onto the x-y surface
            'x'
                Traction acting in x-direction proportional to the area
            'y'
                Traction acting in y-direction proportional to the area
            'z'
                Traction acting in z-direction proportional to the area
            
        time_func : function object
            Function object returning a value between -1 and 1 given the 
            input t: 

            >>> val = time_func(t)
            
        mesh_prop : str {'phys_group', 'geom_entity', 'el_type'}, optional
            label of which the element should be chosen from. Default is 
            phys_group. 
            
        Returns
        -------
        None
        '''
        self.mesh_class.select_neumann_bc(key=key, val=val, direct=direct, 
                                          time_func=time_func, mesh_prop=mesh_prop)
        self.assembly_class.compute_element_indices()
        
    def apply_neumann_boundaries_old(self, neumann_boundary_list):
        '''Apply neumann-boundaries to the system.

        Parameters
        ----------
        neumann_boundary_list : list
            list containing the neumann boundary NB lists:

            >>> NB = [dofs_list, type, properties, B_matrix=None]

        Notes
        -----
        the neumann_boundary_list is a list containing the neumann_boundaries:

        >>> [dofs_list, load_type, properties, B_matrix=None]

        dofs_list : list
            list containig the dofs which are loaded
        load_type : str out of {'stepload', 'dirac', 'harmonic', 'ramp', 'static'}
            string specifying the load type
        properties : tupel
            tupel with the properties for the given load_type (see table below)
        B_matrix : ndarray / None
            Vector giving the load weights for the given dofs in dofs_list. 
            If None is chosen, the weight will be 1 for every dof by default.

        the load_type-Keywords and the corresponding properties are:


        ===========  =====================
        load_type    properties
        ===========  =====================
        'stepload'   (amplitude, time)
        'dirac'      (amplitude, time)
        'harmonic'   (amplitude, frequency)
        'ramp'       (slope, time)
        'static'      (amplitude)
        ===========  =====================

        Examples
        --------

        Stepload on dof 1, 2 and 3 starting at 0.1 s with amplitude 1KN:

        >>> mysystem = MechanicalSystem()
        >>> NB = [[1, 2, 3], 'stepload', (1E3, 0.1), None]
        >>> mysystem.apply_neumann_boundaries([NB, ])

        Harmonic loading on dof 4, 6 and 8 with frequency 8 Hz = 2*2*pi rad and amplitude 100N:

        >>> mysystem = MechanicalSystem()
        >>> NB = [[1, 2, 3], 'harmonic', (100, 8), None]
        >>> mysystem.apply_neumann_boundaries([NB, ])


        '''
        self.neumann_class = NeumannBoundary(self.no_of_dofs, neumann_boundary_list)
        self._f_ext_unconstr = self.neumann_class.f_ext()


    def export_paraview(self, filename):
        '''Export the system with the given information to paraview
        '''
        if len(self.T_output) is 0:
            self.T_output.append(0)
            self.u_output.append(np.zeros(self.no_of_dofs))
        print('Start exporting mesh for paraview to', filename)
        self.mesh_class.set_displacement_with_time(self.u_output, self.T_output)
        self.mesh_class.save_mesh_for_paraview(filename)
        print('Mesh for paraview successfully exported')
        pass

    def M(self):
        '''
        Compute the Mass matrix of the dynamical system. 
        
        Parameters
        ----------
        None
        
        Returns
        -------
        M : sp.sparse.sparse_matrix
            Mass matrix with applied constraints in sparse csr-format
        '''
        M_unconstr = self.assembly_class.assemble_m()
        self._M = self.constrain_matrix(M_unconstr)
        return self._M

    def K(self, u=None, t=0):
        '''
        Compute the stiffness matrix of the mechanical system
        
        Parameters
        ----------
        u : ndarray, optional
            Displacement field in voigt notation
        
        Returns
        -------
        K : sp.sparse.sparse_matrix
            Stiffness matrix with applied constraints in sparse csr-format
        '''
        if u is None:
            u = np.zeros(self.dirichlet_class.no_of_constrained_dofs)
        # Assembled stiffness matrix without dirichlet boundary conditions imposed
        K_unconstr, f_unconstr = self.assembly_class.assemble_k_and_f(
                                    self.unconstrain_vec(u), t) 
        # Apply dirichlet boundary conditions by matrix product (B.T @ K @ B)
        self._K = self.constrain_matrix(K_unconstr)
        return self._K

    def f_int(self, u, t=0):
        '''Return the elastic restoring force of the system '''
        K_unconstr, f_unconstr = self.assembly_class.assemble_k_and_f(
                                    self.unconstrain_vec(u), t) 
        self._f = self.constrain_vec(f_unconstr)
        return self._f

    def _f_ext_unconstr(self, t):
        return np.zeros(self.mesh_class.no_of_dofs)
        
    def f_ext(self, u, du, t):
        '''
        Return the nonlinear external force of the right hand side 
        of the equation, i.e. the excitation.
        '''
        return self.constrain_vec(self._f_ext_unconstr(t))

    def K_and_f(self, u=None, t=0):
        '''
        Compute tangential stiffness matrix and nonlinear force vector 
        in one assembly run.
        '''
        if u is None:
            u = np.zeros(self.dirichlet_class.no_of_constrained_dofs)
        K_unconstr, f_unconstr = self.assembly_class.assemble_k_and_f(
                                    self.unconstrain_vec(u), t)
        self._K = self.constrain_matrix(K_unconstr)
        self._f = self.constrain_vec(f_unconstr)
        return self._K, self._f

    def write_timestep(self, t, u):
        '''
        write the timestep to the mechanical_system class
        '''
        self.T_output.append(t)
        self.u_output.append(self.unconstrain_vec(u))



class ReducedSystem(MechanicalSystem):
    '''
    Class for reduced systems. It is directyl inherited from MechanicalSystem.
    Provides the interface for an integration scheme and so on where a basis 
    vector is to be chosen...


    Parameters
    ----------
    V_basis : ndarray, optional
        Basis onto which the problem will be projected with an Galerkin-Projection.

    Notes
    -----
    The Basis V is a Matrix with x = V*q mapping the reduced set of coordinates 
    q onto the physical coordinates x. The coordinates x are constrained, i.e. 
    the x denotes the full system in the sense of the problem set and not of 
    the pure finite element set.

    The system runs without providing a V_basis when constructing the method 
    only for the unreduced routines.

    Examples
    --------
    TODO

    '''

    def __init__(self, V_basis=None, **kwargs):
        MechanicalSystem.__init__(self, **kwargs)
        self.V = V_basis

    def K_and_f(self, u):
        u_full = self.V.dot(u)
        self._K_unreduced, self._f_unreduced = MechanicalSystem.K_and_f(self, u_full)
        self._K_reduced = self.V.T.dot(self._K_unreduced.dot(self.V))
        self._f_int_reduced = self.V.T.dot(self._f_unreduced)
        return self._K_reduced, self._f_int_reduced


    def K(self, u):
        return self.V.T.dot(MechanicalSystem.K(self, self.V.dot(u)).dot(self.V))

    def f_ext(self, u, du, t):
        return self.V.T.dot(MechanicalSystem.f_ext(self, self.V.dot(u), du, t))

    def f_int(self, u):
        return self.V.T.dot(MechanicalSystem.f_int(self, self.V.dot(u)))

    def M(self):
        return self.V.T.dot(MechanicalSystem.M(self).dot(self.V))

    def write_timestep(self, t, u):
        MechanicalSystem.write_timestep(self, t, self.V.dot(u))

    def K_unreduced(self, u=None):
        '''
        unreduced Stiffness Matrix
        '''
        return MechanicalSystem.K(self, u)

    def f_int_unreduced(self, u):
        return MechanicalSystem.f_int(self, u)

    def M_unreduced(self):
        return MechanicalSystem.M(self)



class ConstrainedMechanicalSystem():
    '''
    Mechanical System with constraints providing the interface for solvers.

    This is an anonymous class providing all interface functions with zero-outputs. 
    For practical use, inherit this class and overwrite the functions needed.

    '''

    def __init__(self):
        self.ndof = 0
        self.ndof_const = 0
        pass

    def M(self, q, dq):
        '''
        Return the mass matrix.

        Parameters
        ----------
        q : ndarray
            generalized position
        dq : ndarray
            generalized velocity

        Returns
        -------
        M : ndarray
            mass matrix of the system
        '''
        return np.zeros((self.ndof, self.ndof))

    def D(self, q, dq):
        '''
        Return the tangential damping matrix.

        The tangential damping matrix is the jacobian matrix of the nonlinear 
        forces with respect to the generalized velocities q.
        Parameters
        ----------
        q : ndarray
            generalized position
        dq : ndarray
            generalized velocity

        Returns
        -------
        D : ndarray
            tangential damping matrix of the system

        '''
        return np.zeros((self.ndof, self.ndof))

    def K(self, q, dq):
        '''
        Return the tangential stiffness matrix

        Parameters
        ----------
        q : ndarray
            generalized position
        dq : ndarray
            generalized velocity

        Returns
        -------
        K : ndarray
            tangential stiffness matrix of the system

        '''
        return np.zeros((self.ndof, self.ndof))

    def C(self, q, dq, t):
        '''
        Return the residual of the constraints.

        The constraints are given in the canonical form C=0. This function 
        returns the residual of the constraints, i.e. C=res.

        Parameters
        ----------
        q : ndarray
            generalized position
        dq : ndarray
            generalized velocity
        t : float
            current time

        Returns
        -------
        C : ndarray
            residual vector of the constraints

        '''
        return np.zeros(self.ndof_const)

    def B(self, q, dq, t):
        '''
        Return the Jacobian B of the constraints.

        The Jacobian matrix of the constraints B is the partial derivative of 
        the constraint vector C with respect to the generalized coordinates q, 
        i.e. B = dC/dq

        Parameters
        ----------
        q : ndarray
            generalized position
        dq : ndarray
            generalized velocity
        t : float
            current time

        Returns
        -------
        B : ndarray
            Jacobian of the constraint vector with respect to the generalized 
            coordinates
        '''
        return np.zeros((self.ndof_const, self.ndof))

    def f_non(self, q, dq):
        '''
        Nonlinear internal forces of the mechanical system.

        Parameters
        ----------
        q : ndarray
            generalized position
        dq : ndarray
            generalized velocity

        Returns
        -------
        f_non : ndarray
            Nonlinear internal force of the mechanical system

        '''
        return np.zeros(self.ndof)

    def f_ext(self, q, dq, t):
        '''
        External force of the mechanical system.

        This is the right hand side of the canonical dynamic equation giving 
        the external forcing.

        Parameters
        ----------
        q : ndarray
            generalized position
        dq : ndarray
            generalized velocity
        t : float
            current time

        Returns
        -------
        f_ext : ndarray
            External force of the mechanical system

        '''
        return np.zeros(self.ndof)
