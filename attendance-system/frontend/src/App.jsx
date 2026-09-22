import {
  BrowserRouter,
  Routes,
  Route,
} from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import Students from "./pages/Students";
import Attendance from "./pages/Attendance";
import Reports from "./pages/Reports";

function App() {
  return (
    <BrowserRouter>

      <Routes>

        <Route
          path="/"
          element={<Dashboard />}
        />
        <Route
          path="/students"
          element={<Students />}
        />
        <Route

          path="/attendance"

          element={<Attendance />}

        />
        <Route

          path="/reports"

          element={<Reports />}

        />

      </Routes>

    </BrowserRouter>
  );
}

export default App;