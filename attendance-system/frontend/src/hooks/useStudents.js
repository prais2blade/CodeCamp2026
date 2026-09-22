import { useQuery } from "@tanstack/react-query";

import {
    getStudents
} from "../api/studentApi";

export function useStudents() {

    return useQuery({

        queryKey: [
            "students"
        ],

        queryFn:
            getStudents

    });

}