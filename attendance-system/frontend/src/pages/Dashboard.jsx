import { useState } from "react";

import DashboardLayout from "../components/layout/DashboardLayout";

import AttendanceTable from "../components/dashboard/AttendanceTable";

import StudentDetailPanel from "../components/dashboard/StudentDetailPanel";

import { useDashboard } from "../hooks/useDashboard";

export default function Dashboard() {

    const {
        data
    } = useDashboard();

    const [
        selectedStudent,
        setSelectedStudent
    ] = useState(null);

    return (

        <DashboardLayout>

            <h1 className="text-3xl font-bold mb-6">
                Attendance Dashboard
            </h1>

            {/* KPI Cards */}

            <div className="grid grid-cols-4 gap-6">

                <div className="bg-slate-900 p-6 rounded-xl">

                    <p className="text-slate-400">
                        Total Students
                    </p>

                    <h2 className="text-4xl font-bold mt-2">

                        {data?.total_students ?? 0}

                    </h2>

                </div>

                <div className="bg-slate-900 p-6 rounded-xl">

                    <p className="text-slate-400">
                        Present Today
                    </p>

                    <h2 className="text-4xl font-bold text-green-400 mt-2">

                        {data?.present ?? 0}

                    </h2>

                </div>

                <div className="bg-slate-900 p-6 rounded-xl">

                    <p className="text-slate-400">
                        Checked Out
                    </p>

                    <h2 className="text-4xl font-bold text-blue-400 mt-2">

                        {data?.checked_out ?? 0}

                    </h2>

                </div>

                <div className="bg-slate-900 p-6 rounded-xl">

                    <p className="text-slate-400">
                        Absent
                    </p>

                    <h2 className="text-4xl font-bold text-red-400 mt-2">

                        {data?.absent ?? 0}

                    </h2>

                </div>

            </div>

            {/* Attendance Table + Student Panel */}

            <div className="grid grid-cols-12 gap-6 mt-8">

                <div className="col-span-8">

                    <AttendanceTable
                        onSelectStudent={
                            setSelectedStudent
                        }
                    />

                </div>

                <div className="col-span-4">

                    <StudentDetailPanel
                        studentId={
                            selectedStudent?.student_id
                        }
                    />

                </div>

            </div>

        </DashboardLayout>

    );

}