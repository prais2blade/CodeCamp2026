import { useState } from "react";

import DashboardLayout from "../components/layout/DashboardLayout";
import StudentDrawer from "../components/students/StudentDrawer";

import { useStudents } from "../hooks/useStudents";

export default function Students() {

    const { data: students = [] } = useStudents();

    const [search, setSearch] = useState("");
    const [selectedClass, setSelectedClass] = useState("All");

    const [selectedStudent, setSelectedStudent] = useState(null);
    const [drawerOpen, setDrawerOpen] = useState(false);

    const classes = [

        "All",

        ...new Set(

            students
                .map(student => student.class_name)
                .filter(Boolean)

        )

    ];

    const filteredStudents = students.filter(student => {

        const fullName = (

            student.first_name +
            " " +
            student.last_name

        ).toLowerCase();

        const matchesSearch = fullName.includes(
            search.toLowerCase()
        );

        const matchesClass =

            selectedClass === "All"

            ||

            student.class_name === selectedClass;

        return matchesSearch && matchesClass;

    });

    return (

        <DashboardLayout>

            {/* Header */}

            <div className="flex justify-between items-center mb-8">

                <h1 className="text-4xl font-bold">

                    Students

                </h1>

                <div className="flex gap-3">

                    <select

                        value={selectedClass}

                        onChange={(e) =>

                            setSelectedClass(
                                e.target.value
                            )

                        }

                        className="
                            bg-slate-900
                            border
                            border-slate-700
                            rounded-lg
                            px-4
                            py-2
                        "

                    >

                        {classes.map((cls) => (

                            <option

                                key={cls}

                                value={cls}

                            >

                                {cls}

                            </option>

                        ))}

                    </select>

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
                            bg-slate-900
                            border
                            border-slate-700
                            rounded-lg
                            px-4
                            py-2
                        "

                    />

                </div>

            </div>

            {/* Student Cards */}

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">

                {filteredStudents.map((student) => (

                    <div

                        key={student.student_id}

                        className="
                            bg-slate-900
                            rounded-xl
                            p-6
                            shadow-lg
                        "

                    >

                        {/* Top Section */}

                        <div className="flex items-center gap-4 mb-4">

                            {student.photo ? (

                                <img

                                    src={student.photo}

                                    alt={student.first_name}

                                    className="
                                        h-16
                                        w-16
                                        rounded-full
                                        object-cover
                                    "

                                />

                            ) : (

                                <div

                                    className="
                                        h-16
                                        w-16
                                        rounded-full
                                        bg-slate-700
                                    "

                                />

                            )}

                            <div>

                                <h3 className="font-bold text-xl">

                                    {student.first_name}{" "}
                                    {student.last_name}

                                </h3>

                                <p className="text-slate-400">

                                    {student.student_id}

                                </p>

                            </div>

                        </div>

                        {/* Details */}

                        <div className="space-y-2 mb-4">

                            <p>

                                <strong>Class:</strong>{" "}
                                {student.class_name || "N/A"}

                            </p>

                            <p>

                                <strong>Parent:</strong>{" "}
                                {student.parent_name || "N/A"}

                            </p>

                        </div>

                        {/* Status */}

                        <div className="mb-5">

                            <span

                                className="
                                    bg-green-600
                                    text-white
                                    text-xs
                                    px-3
                                    py-1
                                    rounded-full
                                "

                            >

                                Active

                            </span>

                        </div>

                        {/* Buttons */}

                        <div className="flex gap-2">

                            <button

                                onClick={() => {

                                    setSelectedStudent(
                                        student.student_id
                                    );

                                    setDrawerOpen(true);

                                }}

                                className="
                                    bg-blue-600
                                    hover:bg-blue-700
                                    px-4
                                    py-2
                                    rounded-lg
                                    text-sm
                                "

                            >

                                View

                            </button>

                            <button

                                className="
                                    bg-amber-600
                                    hover:bg-amber-700
                                    px-4
                                    py-2
                                    rounded-lg
                                    text-sm
                                "

                            >

                                Edit

                            </button>

                            <button

                                className="
                                    bg-purple-600
                                    hover:bg-purple-700
                                    px-4
                                    py-2
                                    rounded-lg
                                    text-sm
                                "

                            >

                                Portal

                            </button>

                        </div>

                    </div>

                ))}

            </div>

            {/* Drawer */}

            <StudentDrawer

                studentId={selectedStudent}

                isOpen={drawerOpen}

                onClose={() =>

                    setDrawerOpen(false)

                }

            />

        </DashboardLayout>

    );

}