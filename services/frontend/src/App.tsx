import { Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import PageHome from "./pages/PageHome";
import PageResults from "./pages/PageResults";

/**
 * Корневой компонент: маршруты приложения внутри общего лэйаута.
 * `/` — главная, `/results` — результаты батча (frontend.md, раздел 6.1).
 */
export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<PageHome />} />
        <Route path="results" element={<PageResults />} />
      </Route>
    </Routes>
  );
}
