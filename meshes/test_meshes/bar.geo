cl__1 = 1;
Point(1) = {0, 0, 0, 1};
Point(2) = {2, 0, 0, 1};
Point(3) = {2, 0.5, 0, 1};
Point(4) = {0, 0.5, 0, 1};
Line(1) = {1, 2};
Line(2) = {2, 3};
Line(3) = {3, 4};
Line(4) = {4, 1};
Line Loop(6) = {3, 4, 1, 2};
Plane Surface(6) = {6};
