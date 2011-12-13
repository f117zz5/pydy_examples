from sympy import (symbols, ccode, Symbol, cse, numbered_symbols, sqrt)
from sympy.physics.mechanics import (dynamicsymbols, ReferenceFrame, Vector,
    Point, inertia, dot, cross)

Vector.simp = False         # Prevent the use of trigsimp and simplify
t, g = symbols('t g')       # Time and gravitational constant
a, b, c = symbols('a b c')  # semi diameters of ellipsoid
d, e, f = symbols('d e f')  # mass center location parameters
s = symbols('s')            # coefficient of viscous friction

# Mass and Inertia scalars
m, Ixx, Iyy, Izz, Ixy, Iyz, Ixz = symbols('m Ixx Iyy Izz Ixy Iyz Ixz')

q = dynamicsymbols('q:3')             # Generalized coordinates
qd = [qi.diff(t) for qi in q]         # Generalized coordinate time derivatives
r = dynamicsymbols('r:3')             # Coordinates, in R frame, from O to P
rd = [ri.diff(t) for ri in r]         # Time derivatives of xi

N = ReferenceFrame('N')                   # Inertial Reference Frame
Y = N.orientnew('Y', 'Axis', [q[0], N.z]) # Yaw Frame
L = Y.orientnew('L', 'Axis', [q[1], Y.x]) # Lean Frame
R = L.orientnew('R', 'Axis', [q[2], L.y]) # Rattleback body fixed frame

I = inertia(R, Ixx, Iyy, Izz, Ixy, Iyz, Ixz)    # Inertia dyadic

# Angular velocity using u's as body fixed measure numbers of angular velocity
R.set_ang_vel(N, qd[0]*Y.z + qd[1]*Y.x + qd[2]*L.y)

# Rattleback ground contact point
P = Point('P')

# Rattleback ellipsoid center location, see:
# "Realistic mathematical modeling of the rattleback", Kane, Thomas R. and
# David A. Levinson, 1982, International Journal of Non-Linear Mechanics
mu = [dot(rk, Y.z) for rk in R]
eps = sqrt((a*mu[0])**2 + (b*mu[1])**2 + (c*mu[2])**2)
O = P.locatenew('O', -a*a*mu[0]/eps*R.x
                     -b*b*mu[1]/eps*R.y
                     -c*c*mu[2]/eps*R.z)
O.set_vel(N, cross(R.ang_vel_in(N), O.pos_from(P)))

# Mass center position and velocity
RO = O.locatenew('RO', d*R.x + e*R.y + f*R.z)
RO.set_vel(N, O.vel(N) + cross(R.ang_vel_in(N), RO.pos_from(O)))

# Partial angular velocities and partial velocities
partial_w = [R.ang_vel_in(N).diff(qdi, N) for qdi in qd]
partial_v_RO = [RO.vel(N).diff(qdi, N) for qdi in qd]

steady_dict = {qd[1]: 0, qd[2]: 0,
               qd[0].diff(t): 0, qd[1].diff(t): 0, qd[2].diff(t): 0}

# Set auxiliary generalized speeds to zero in velocity vectors
O.set_vel(N, O.vel(N).subs(steady_dict))
RO.set_vel(N, RO.vel(N).subs(steady_dict))
R.set_ang_vel(N, R.ang_vel_in(N).subs(steady_dict))

# Verify the derivative of v^{RO} taken in the R frame is zero under the
# conditions of steady motion
assert(RO.vel(N).diff(t, R).subs(steady_dict) == 0)
# Acceleration of mass center
RO.set_acc(N, cross(R.ang_vel_in(N), RO.vel(N)))

# Forces and Torques
F_RO = m*g*Y.z

# Generalized Active forces
gaf_RO = [dot(F_RO, pv) for pv in partial_v_RO]

# Generalized Inertia forces
R_star = - m*RO.acc(N)
# Angular acceleration is zero
T_star = - cross(R.ang_vel_in(N), dot(I, R.ang_vel_in(N)))

# Steady dynamic equations
f_r = [0]*3
f_r_star = [0]*3
f_dyn = [0]*3
for i in range(3):
  f_r[i] = gaf_RO[i].expand().collect(m*g)
  f_r_star[i] = (dot(R_star, partial_v_RO[i]) + dot(T_star, partial_w[i])).expand().collect(qd[0]**2)
  f_dyn[i] = f_r[i] + f_r_star[i]
  assert(f_dyn[i].diff(q[0]) == 0)

# Verify that the first dynamic equation is zero
assert(f_dyn[0] == 0)

# The remaining two steady dynamic equations are of the form:
# h_0 + h_1*qd[0]**2 = 0
# h_1 + h_2*qd[0]**2 = 0

# Get the expressions for each of the g's
h = [0]*4
for i in range(2):
  h[2*i] = f_dyn[i + 1].subs({qd[0]:0})
  h[2*i + 1] = f_dyn[i + 1].coeff(qd[0]**2)

# Form expressions for derivatives of the g's w.r.t. lean and pitch
dh = [0]*8
for i in range(4):
  for j in range(2):
    dh[2*i + j] = h[i].diff(q[j+1])

# Subsitution dictionary to replace dynamic symbols with regular symbols
symbol_dict = {q[1]: Symbol('q1'), q[2]: Symbol('q2'), qd[0]: Symbol('qd0'),
               r[0]: Symbol('rx'), r[1]: Symbol('ry'),  r[2]: Symbol('rz')}

for i in range(4):
  h[i] = h[i].subs(symbol_dict)
for i in range(8):
  dh[i] = dh[i].subs(symbol_dict)

# CSE on g's
z, h_red = cse(h, numbered_symbols('z'))

# Form output code for g's
output_code = "  // Intermediate variables for h's\n"
for zi_lhs, zi_rhs in z:
  output_code += "  {0} = {1};\n".format(zi_lhs, ccode(zi_rhs))

output_code += "\n  // h's\n"
for i in range(4):
  output_code += "  h[{0}] = {1};\n".format(i, ccode(h_red[i]))

# CSE on dh's
z, dh_red = cse(dh, numbered_symbols('z'))

# Form output code for dg's
output_code += "\n  // Intermediate variables for dh's\n"
for zi_lhs, zi_rhs in z:
  output_code += "  {0} = {1};\n".format(zi_lhs, ccode(zi_rhs))

output_code += "\n  // dh's\n"
for i in range(8):
  output_code += "  dh[{0}] = {1};\n".format(i, ccode(dh_red[i]))

# Perform text substitutions to change symbols used for state variables and
# their derivatives (qi, ui, qdi, udi) to the names used by the ode integrator.
import re
output_code = re.sub(r"z(\d+)", r"z[\1]", output_code)

f = file("ellipsoid_no_slip_steady.txt", 'w')
f.write(output_code)
f.close()
