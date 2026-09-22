import StudentDetailPanel from "../dashboard/StudentDetailPanel";
export default function StudentDrawer({

    studentId,

    isOpen,

    onClose

}) {

    if (!isOpen) {

        return null;

    }

    return (

        <>

            <div

                onClick={onClose}

                className="
                    fixed
                    inset-0
                    bg-black/50
                    z-40
                "

            />

            <div

                className="
                    fixed
                    top-0
                    right-0
                    h-full
                    w-112.5
                    bg-slate-950
                    border-l
                    border-slate-800
                    z-50
                    overflow-y-auto
                    p-4
                "

            >

                <div className="flex justify-between items-center mb-4">

                    <h2 className="text-xl font-bold">

                        Student Profile

                    </h2>

                    <button

                        onClick={onClose}

                        className="
                            bg-red-600
                            px-3
                            py-2
                            rounded
                        "

                    >

                        Close

                    </button>

                </div>

                <StudentDetailPanel

                    studentId={studentId}

                />

            </div>

        </>

    );

}