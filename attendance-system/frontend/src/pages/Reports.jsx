import DashboardLayout from "../components/layout/DashboardLayout";

import {
    useReportSummary,
    useStudentStats,
    useAttendanceTrend
} from "../hooks/useReports";

import AttendanceChart
    from "../components/reports/AttendanceChart";

export default function Reports() {

    const {
        data: summary = {}
    } = useReportSummary();

    const {
        data: stats = []
    } = useStudentStats();

    const {
        data: trend = []
    } = useAttendanceTrend();


    return (

        <DashboardLayout>

            <h1 className="text-4xl font-bold mb-8">

                Reports

            </h1>
            <div className="mb-6">

                <button

                    onClick={() =>

                        window.open(
                            "http://127.0.0.1:8000/api/reports/export/excel/",
                            "_blank"
                        )

                    }

                    className="
            bg-green-600
            hover:bg-green-700
            px-4
            py-2
            rounded-lg
            font-medium
        "

                >

                    Export Excel

                </button>

                <button

                    onClick={() =>

                        window.open(

                            "http://127.0.0.1:8000/api/reports/export/students/",

                            "_blank"

                        )

                    }

                    className="
        bg-blue-600
        hover:bg-blue-700
        px-4
        py-2
        rounded-lg
        font-medium
        ml-3
    "

                >

                    Export Students

                </button>

                <button

                    onClick={() =>

                        window.open(

                            "http://127.0.0.1:8000/api/reports/export/csv/",

                            "_blank"

                        )

                    }

                    className="
        bg-purple-600
        hover:bg-purple-700
        px-4
        py-2
        rounded-lg
        ml-3
    "

                >

                    Export CSV

                </button>

            </div>

            <div className="grid md:grid-cols-4 gap-4 mb-8">

                <div className="bg-slate-900 p-5 rounded-xl">
                    <p>Total Students</p>
                    <h2 className="text-4xl font-bold">
                        {summary.total_students || 0}
                    </h2>
                </div>

                <div className="bg-slate-900 p-5 rounded-xl">
                    <p>Present Today</p>
                    <h2 className="text-4xl font-bold text-green-400">
                        {summary.present_today || 0}
                    </h2>
                </div>

                <div className="bg-slate-900 p-5 rounded-xl">
                    <p>Checked Out</p>
                    <h2 className="text-4xl font-bold text-blue-400">
                        {summary.checked_out || 0}
                    </h2>
                </div>

                <div className="bg-slate-900 p-5 rounded-xl">
                    <p>Absent</p>
                    <h2 className="text-4xl font-bold text-red-400">
                        {summary.absent || 0}
                    </h2>
                </div>

            </div>

            <div className="bg-slate-900 rounded-xl p-6 mb-6">

                <h2 className="text-2xl font-bold mb-4">

                    🏆 Top Attendees

                </h2>

                {stats
                    .slice(0, 5)
                    .map(student => (

                        <div
                            key={student.student_id}
                            className="
                    flex
                    justify-between
                    py-2
                    border-b
                    border-slate-800
                "
                        >

                            <span>

                                {student.name}

                            </span>

                            <span className="text-green-400">

                                {student.attendance_percent}%

                            </span>

                        </div>

                    ))
                }

            </div>

            <AttendanceChart
                data={trend}
            />

            <div className="bg-slate-900 rounded-xl p-6">

                <h2 className="text-2xl font-bold mb-4">

                    Attendance Statistics

                </h2>

                <table className="w-full">

                    <thead>

                        <tr>

                            <th className="text-left py-3">
                                Student ID
                            </th>

                            <th className="text-left">
                                Name
                            </th>

                            <th className="text-left">
                                Attendance %
                            </th>

                        </tr>

                    </thead>

                    <tbody>

                        {stats.map(student => (

                            <tr
                                key={student.student_id}
                                className="border-t border-slate-800"
                            >

                                <td className="py-4">
                                    {student.student_id}
                                </td>

                                <td>
                                    {student.name}
                                </td>

                                <td>
                                    {student.attendance_percent}%
                                </td>

                            </tr>

                        ))}

                    </tbody>

                </table>

            </div>

        </DashboardLayout>

    );

}