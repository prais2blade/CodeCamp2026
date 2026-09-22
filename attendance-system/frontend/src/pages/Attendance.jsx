import { useState } from "react";

import DashboardLayout from "../components/layout/DashboardLayout";

import { useAttendance } from "../hooks/useAttendance";

export default function Attendance() {

    const {

        data: attendance = [],

        isLoading

    } = useAttendance();

    const [search, setSearch] = useState("");

    const filteredAttendance = attendance.filter(

        item =>

            item.name
                .toLowerCase()
                .includes(
                    search.toLowerCase()
                )

    );
    const presentCount = attendance.length;

    const inCenterCount = attendance.filter(

        item => item.status === "IN CENTER"

    ).length;

    const checkedOutCount = attendance.filter(

        item => item.status === "CHECKED OUT"

    ).length;

    return (

        <DashboardLayout>

            <div className="mb-8">

                <h1 className="text-4xl font-bold mb-4">

                    Attendance

                </h1>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">

                    <div className="bg-slate-900 p-5 rounded-xl">

                        <p className="text-slate-400">

                            Present

                        </p>

                        <h2 className="text-4xl font-bold">

                            {presentCount}

                        </h2>

                    </div>

                    <div className="bg-slate-900 p-5 rounded-xl">

                        <p className="text-slate-400">

                            In Center

                        </p>

                        <h2 className="text-4xl font-bold text-green-400">

                            {inCenterCount}

                        </h2>

                    </div>

                    <div className="bg-slate-900 p-5 rounded-xl">

                        <p className="text-slate-400">

                            Checked Out

                        </p>

                        <h2 className="text-4xl font-bold text-blue-400">

                            {checkedOutCount}

                        </h2>

                    </div>

                    <div className="bg-slate-900 p-5 rounded-xl">

                        <p className="text-slate-400">

                            Absent

                        </p>

                        <h2 className="text-4xl font-bold text-red-400">

                            TBD

                        </h2>

                    </div>

                </div>

                <input

                    type="text"

                    placeholder="Search student..."

                    value={search}

                    onChange={(e) =>

                        setSearch(
                            e.target.value
                        )

                    }

                    className="
                        w-full
                        md:w-96
                        bg-slate-900
                        border
                        border-slate-700
                        rounded-lg
                        px-4
                        py-3
                    "

                />

            </div>

            {isLoading ? (

                <div>

                    Loading...

                </div>

            ) : (

                <div className="bg-slate-900 rounded-xl p-6">

                    <table className="w-full">

                        <thead>

                            <tr className="border-b border-slate-700">

                                <th className="text-left py-3">

                                    Student ID

                                </th>

                                <th className="text-left">

                                    Name

                                </th>

                                <th className="text-left">

                                    Class

                                </th>

                                <th className="text-left">

                                    Check In

                                </th>

                                <th className="text-left">

                                    Status

                                </th>

                            </tr>

                        </thead>

                        <tbody>

                            {filteredAttendance.map(

                                student => (

                                    <tr

                                        key={
                                            student.student_id
                                        }

                                        className="
                                            border-b
                                            border-slate-800
                                        "

                                    >

                                        <td className="py-4">

                                            {
                                                student.student_id
                                            }

                                        </td>

                                        <td>

                                            {
                                                student.name
                                            }

                                        </td>

                                        <td>

                                            {
                                                student.class_name
                                                ||
                                                "N/A"
                                            }

                                        </td>

                                        <td>

                                            {
                                                student.check_in
                                            }

                                        </td>

                                        <td>

                                            <span

                                                className="
                                                    bg-green-600
                                                    px-3
                                                    py-1
                                                    rounded-full
                                                    text-xs
                                                "

                                            >

                                                {
                                                    student.status
                                                }

                                            </span>

                                        </td>

                                    </tr>

                                )

                            )}

                        </tbody>

                    </table>

                </div>

            )}

        </DashboardLayout>

    );

}